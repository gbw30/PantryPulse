"""Real loopback HTTP smoke using configured private demo access; never fake a worker."""

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--access-file", type=Path, required=True)
    parser.add_argument(
        "--read-only", action="store_true", help="Check new read APIs without submitting jobs"
    )
    args = parser.parse_args()
    access = json.loads(args.access_file.read_text(encoding="utf-8-sig"))
    manifest = (
        None
        if args.read_only
        else json.loads(Path(access["request_file"]).read_text(encoding="utf-8-sig"))
    )
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--env-file",
            str(args.env_file.resolve()),
        ],
        cwd=Path(__file__).resolve().parents[1],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=30) as client:
            deadline = time.monotonic() + 40
            while True:
                try:
                    if client.get("/api/v1/health").status_code == 200:
                        break
                except httpx.ConnectError:
                    pass
                if process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError("LOCAL_SERVER_NOT_READY")
                time.sleep(0.25)
            origin = {"Origin": "http://127.0.0.1:3000"}
            login = client.post(
                "/api/v1/presenter/login",
                json={"username": access["username"], "password": access["password"]},
                headers=origin,
            )
            if login.status_code != 200:
                raise RuntimeError(f"LOGIN_HTTP_{login.status_code}")
            headers = origin | {"X-CSRF-Token": login.json()["csrf_token"]}
            catalog = client.get("/api/v1/forecast-catalog")
            if catalog.status_code != 200:
                raise RuntimeError(f"CATALOG_HTTP_{catalog.status_code}")
            data = catalog.json()
            assert len(data["sites"]) == 7 and len(data["products"]) == 2
            if args.read_only:
                results = {}
                for path in (
                    "operational-catalog",
                    "dashboard/summary",
                    "supplies",
                    "allocation-methodology",
                    "scenarios",
                ):
                    response = client.get(f"/api/v1/{path}")
                    if response.status_code != 200:
                        raise RuntimeError(f"READ_{path}_HTTP_{response.status_code}")
                    results[path] = response.status_code
                assert client.post("/api/v1/presenter/logout", headers=headers).status_code == 200
                print(
                    json.dumps(
                        {
                            "transport": "REAL_LOOPBACK_HTTP",
                            "login": 200,
                            "reads": results,
                            "logout": 200,
                        }
                    )
                )
                return 0
            submitted = client.post(
                "/api/v1/forecasts",
                json=manifest["request"],
                headers=(headers | {"Idempotency-Key": "configured-http-smoke-v1"}),
            )
            if submitted.status_code == 503:
                assert submitted.json()["error"]["code"] == "COMPUTE_UNAVAILABLE"
                outcome = "COMPUTE_UNAVAILABLE (correctly requires a live Linux worker)"
            elif submitted.status_code == 202:
                outcome = "ACCEPTED; computation must be checked via returned job URLs"
            else:
                raise RuntimeError(f"FORECAST_HTTP_{submitted.status_code}")
            assert client.post("/api/v1/presenter/logout", headers=headers).status_code == 200
            print(
                json.dumps(
                    {
                        "transport": "REAL_LOOPBACK_HTTP",
                        "login": 200,
                        "catalog": 200,
                        "sites": len(data["sites"]),
                        "products": len(data["products"]),
                        "sources": len(data["sources"]),
                        "forecast_submission": outcome,
                    }
                )
            )
        return 0
    except (RuntimeError, AssertionError, httpx.HTTPError) as error:
        # No request/response bodies, passwords, cookies, SQL or database URLs in output.
        print(f"HTTP smoke failed: {type(error).__name__}", file=sys.stderr)
        if isinstance(error, RuntimeError):
            print(str(error), file=sys.stderr)
        return 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
