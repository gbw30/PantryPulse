"""Explicit real HTTP/PostgreSQL/Linux/Chronos journey in one disposable test schema.

Requires PP_TEST_DATABASE_URL naming a *_test database and the trusted opt-in
Chronos configuration/cache. Starts only its own loopback server and supervisor;
never migrates an existing schema or stops an existing runtime. No final holdout.
"""

import argparse
import hashlib
import json
import os
import socket
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import sqlalchemy as sa
import uvicorn
from alembic import command
from alembic.config import Config
from sqlalchemy.engine import make_url

from app.database import database_engine
from app.main import create_app
from app.repositories.forecast_results import read_committed_forecast
from app.repositories.jobs import QueueRepository, create_queue_engine
from app.services.chronos_runtime import CHRONOS_CONTRACT, execution_capability
from app.services.forecast_runtime import ForecastRuntime
from app.services.jobs.contracts import PRODUCTION_PROFILE
from app.workers.process_driver import PosixProcessDriver
from app.workers.registries import load_registry
from app.workers.supervisor import Supervisor, SupervisorConfig
from scripts.load_optimization_demo import seed_demo

API_ROOT = Path(__file__).resolve().parents[1]


def wait_for(predicate, timeout=90):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("Dedicated smoke operation did not complete within its test bound")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    url = os.environ.get("PP_TEST_DATABASE_URL")
    if not url or not (make_url(url).database or "").endswith("_test"):
        parser.error("PP_TEST_DATABASE_URL must select a dedicated *_test database")
    capability = execution_capability()
    if capability is None:
        parser.error("Explicit pinned Chronos package/cache capability is unavailable")
    schema = "ppfc84_test_" + uuid4().hex
    admin = database_engine(url)
    runtime = None
    supervisor = None
    worker_stop = threading.Event()
    worker_thread = None
    server = None
    server_thread = None
    listening = None
    summary = {
        "schema_version": "chronos-jobs-smoke-v1",
        "scope": "SIMULATED",
        "generated_at": datetime.now(UTC).isoformat(),
        "capability": capability,
        "schema": schema,
        "production_profile": PRODUCTION_PROFILE.effective_limits(),
    }
    started = time.perf_counter()
    created = False
    try:
        with admin.begin() as connection:
            connection.execute(sa.schema.CreateSchema(schema))
            created = True
            config = Config(str(API_ROOT / "alembic.ini"))
            config.attributes.update(connection=connection, schema=schema)
            command.upgrade(config, "head")
            connection.execute(sa.text(f'SET LOCAL search_path TO "{schema}"'))
            demo = seed_demo(connection)
        engine = create_queue_engine(admin.url, schema=schema)
        registry = load_registry("production")
        queue = QueueRepository(engine, registry=registry, profile=PRODUCTION_PROFILE)
        runtime = ForecastRuntime(engine, queue)
        listening = socket.socket()
        listening.bind(("127.0.0.1", 0))
        listening.listen()
        origin = f"http://127.0.0.1:{listening.getsockname()[1]}"
        password, salt = uuid4().hex, uuid4().hex
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=64
        ).hex()
        os.environ.update(
            PP_PRESENTER_USERNAME="fc84-smoke",
            PP_PRESENTER_PASSWORD_HASH=f"scrypt$16384$8$1${salt}${digest}",
            PP_PRESENTER_ORGANIZATION_ID=demo["organization_id"],
            PP_ALLOWED_ORIGINS=origin,
            PP_COOKIE_SECURE="false",
        )
        server = uvicorn.Server(uvicorn.Config(create_app(runtime), log_level="error"))
        server_thread = threading.Thread(
            target=server.run, kwargs={"sockets": [listening]}, daemon=True
        )
        server_thread.start()
        wait_for(lambda: server.started)
        supervisor = Supervisor(
            queue,
            registry,
            PosixProcessDriver(cwd=API_ROOT, thread_limit=2),
            SupervisorConfig("production", PRODUCTION_PROFILE),
        )
        assert supervisor.start()

        def worker_loop():
            while not worker_stop.is_set():
                supervisor.tick()
                worker_stop.wait(0.02)

        worker_thread = threading.Thread(target=worker_loop, daemon=True)
        worker_thread.start()
        with httpx.Client(base_url=origin, timeout=30) as client:
            auth = client.post(
                "/api/v1/presenter/login",
                json={
                    "username": "fc84-smoke",
                    "password": password,
                },
                headers={"Origin": origin},
            )
            assert auth.status_code == 200
            headers = {"Origin": origin, "X-CSRF-Token": auth.json()["csrf_token"]}

            def post(path, body, expected):
                response = client.post(
                    "/api/v1/" + path, json=body, headers=headers | {"Idempotency-Key": uuid4().hex}
                )
                assert response.status_code == expected, (path, response.status_code, response.text)
                return response.json()

            def terminal(job):
                status = client.get(job["status_url"])
                assert status.status_code == 200
                value = status.json()
                return value if value["state"] not in {"QUEUED", "RUNNING", "STOPPING"} else None

            request = demo["request"] | {
                "policy": demo["request"]["policy"]
                | {
                    "strategy": "CHRONOS2",
                    "allow_fallback": False,
                }
            }
            no_fallback = post("forecasts", request, 202)
            state = wait_for(lambda: terminal(no_fallback))
            assert state["state"] == "SUCCEEDED", state
            partial = client.get(no_fallback["result_url"]).json()
            assert partial["planning_ready"] is False
            assert partial["forecast"]["actual_providers"] == ["CHRONOS2"]
            assert 0 < sum(r["status"] == "AVAILABLE" for r in partial["forecast"]["series"]) < 26
            summary["no_fallback"] = {
                "job_id": no_fallback["job_id"],
                "state": state["state"],
                "planning_ready": partial["planning_ready"],
                "actual_providers": partial["forecast"]["actual_providers"],
                "available_series": sum(
                    r["status"] == "AVAILABLE" for r in partial["forecast"]["series"]
                ),
                "forecast_points": sum(len(r["points"]) for r in partial["forecast"]["series"]),
            }
            fallback_request = request | {"policy": request["policy"] | {"allow_fallback": True}}
            fallback = post("forecasts", fallback_request, 202)
            fallback_state = wait_for(lambda: terminal(fallback))
            assert fallback_state["state"] == "SUCCEEDED", fallback_state
            saved = client.get(fallback["result_url"]).json()
            assert saved["planning_ready"]
            assert saved["forecast"]["actual_providers"] == ["MOVING_AVERAGE"]
            assert all(
                r["fallback_used"] and r["actual_provider"]["checkpoint"] is None
                for r in saved["forecast"]["series"]
            )
            frozen, output = read_committed_forecast(
                engine,
                UUID(demo["organization_id"]),
                UUID(fallback["job_id"]),
            )
            assert output.model_dump(mode="json") == saved["forecast"]
            assert frozen.policy.checkpoint_revision == capability["checkpoint_revision"]
            summary["fallback"] = {
                "job_id": fallback["job_id"],
                "state": fallback_state["state"],
                "planning_ready": True,
                "actual_providers": ["MOVING_AVERAGE"],
                "fallback_series": 26,
                "forecast_points": 182,
            }

            # Run an actual contained child cancellation, then retry the same frozen pin.
            cancelling = post("forecasts", request | {"force_refresh": True}, 202)
            wait_for(lambda: client.get(cancelling["status_url"]).json()["state"] == "RUNNING")
            wait_for(
                lambda: supervisor.active is not None and supervisor.active.current is not None
            )
            handle = supervisor.active.current.handle
            environment = Path(f"/proc/{handle.identity.leader_pid}/environ").read_bytes()
            assert (
                b"DATABASE_URL=" not in environment and b"PP_TEST_DATABASE_URL=" not in environment
            )
            assert b"PP_CHRONOS_MODEL_CACHE=" in environment
            post(f"jobs/{cancelling['job_id']}/cancel", {}, 202)
            cancelled = wait_for(lambda: terminal(cancelling))
            assert cancelled["state"] == "CANCELLED", cancelled
            assert supervisor.driver.confirm_empty(handle.identity)
            retried = post(f"jobs/{cancelling['job_id']}/retry", {}, 202)
            assert retried["job_id"] == cancelling["job_id"]
            assert retried["attempt_id"] != cancelling["attempt_id"]
            retried_state = wait_for(lambda: terminal(retried))
            assert retried_state["state"] == "SUCCEEDED", retried_state
            summary["cancel_retry"] = {
                "cancelled_state": "CANCELLED",
                "boundary_empty": True,
                "retry_state": "SUCCEEDED",
                "same_job_new_attempt": True,
                "database_credentials_absent_in_child": True,
            }

            catalog = client.get("/api/v1/planning-catalog").json()
            assumptions = client.get(
                f"/api/v1/planning-assumptions/{demo['assumptions_id']}"
            ).json()
            scenario = post(
                "scenarios",
                {
                    "forecast_run_id": fallback["job_id"],
                    "assumptions_id": demo["assumptions_id"],
                    "expected_source_revision": catalog["source_revision"],
                    "transfer_mode": "HUB_ONLY",
                    "planning_days": 3,
                    "modifiers": [
                        {
                            "site_id": r["site_id"],
                            "product_id": r["product_id"],
                            "mode": "CENTRAL",
                            "multiplier": "1",
                            "buffer_fraction": None,
                        }
                        for r in assumptions["payload"]["reserves"]
                    ],
                },
                201,
            )
            assert all(
                f["actual_provider"] == "MOVING_AVERAGE"
                for f in scenario["payload"]["package"]["forecasts"]
                if f["actual_provider"] != "DERIVED_HUB_ZERO_DEMAND"
            )
            summary["canonical_scenario"] = {
                "id": scenario["id"],
                "frozen": True,
                "provider": "MOVING_AVERAGE",
            }

            # Stop only this smoke's worker; completed reuse and saved reads stay available.
            worker_stop.set()
            worker_thread.join(10)
            supervisor.shutdown_drain(timeout_s=10)
            duplicate = post("forecasts", fallback_request, 202)
            assert duplicate["job_id"] == fallback["job_id"]
            assert client.get(fallback["result_url"]).json() == saved
            response = client.post(
                "/api/v1/forecasts",
                json=fallback_request | {"force_refresh": True},
                headers=headers | {"Idempotency-Key": uuid4().hex},
            )
            assert response.status_code == 503
            summary["offline_saved_reuse"] = True
            summary["offline_new_computation"] = response.json()["error"]["code"]
            summary["handler_contract"] = CHRONOS_CONTRACT
    finally:
        worker_stop.set()
        if worker_thread is not None:
            worker_thread.join(10)
        if supervisor is not None and not supervisor.closed:
            supervisor.shutdown_immediate(timeout_s=15)
        if server is not None:
            server.should_exit = True
        if server_thread is not None:
            server_thread.join(10)
        if listening is not None:
            listening.close()
        if runtime is not None:
            runtime.engine.dispose()
        if created:
            with admin.begin() as connection:
                connection.execute(sa.schema.DropSchema(schema, cascade=True))
        admin.dispose()
    summary["wall_seconds"] = time.perf_counter() - started
    summary["disposable_schema_removed"] = True
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
