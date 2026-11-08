"""GET /jobs/{job_id} for v1 jobs, which belong to their network's organization (CR-w1-solver-5).

W0-network-model §2: the local session may read every network of the install, and the
server resolves the organization; the client never supplies it.
"""

import uuid
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from fake_driver import FakeDriver
from test_supervisor import PROFILE

from app.repositories.jobs import JobNotFound, QueueRepository, TrustedScope
from app.routers.forecasts import job_status
from app.services.jobs.contracts import AttemptState, OperationKind
from app.services.jobs.registry import Registration, Registry
from app.workers.supervisor import Supervisor, SupervisorConfig
from app.workers.testing import EchoHandler, FixturePublisher

pytestmark = pytest.mark.integration

ECHO = {"value": 1, "behavior": {}}
REGISTRY = Registry(
    [
        Registration(
            contract=contract,
            operation_kind=OperationKind.COMPARISON,
            input_schema_version="1",
            max_input_bytes=16_384,
            max_output_bytes=65_536,
            handler=EchoHandler(),
            publisher=FixturePublisher("echo"),
        )
        for contract in ("or-comparison.v3", "or-comparison.v2", "forecast.v1")
    ]
)


@pytest.fixture
def install(db):
    """A network organization, the presenter's own organization and an unrelated one."""
    net_org, own, stranger = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    with db.begin() as conn:
        for org in (net_org, own, stranger):
            conn.execute(
                sa.text("INSERT INTO organizations (id, name, is_demo) VALUES (:o, 'o', false)"),
                {"o": org},
            )
        conn.execute(
            sa.text(
                "INSERT INTO networks (id, organization_id, name, mode, timezone) "
                "VALUES (:n, :o, 'n', 'PANTRY', 'America/New_York')"
            ),
            {"n": uuid.uuid4(), "o": net_org},
        )
    repo = QueueRepository(db, registry=REGISTRY, profile=PROFILE)
    config = SupervisorConfig(registry_name="test", profile=PROFILE, tick_s=0.02)
    sup = Supervisor(repo, REGISTRY, FakeDriver(registry=REGISTRY), config)
    assert sup.start()  # advertise only; never ticks, so jobs stay QUEUED
    yield SimpleNamespace(
        rt=SimpleNamespace(queue=repo, engine=db),
        presenter=TrustedScope(own, "presenter"),
        network=TrustedScope(net_org, "presenter"),
        stranger=TrustedScope(stranger, "someone"),
    )
    sup.close()


def _submit(install, scope, contract):
    return install.rt.queue.submit(scope, contract, ECHO, str(uuid.uuid4())).job_id


def test_v1_job_of_an_install_network_is_visible(install):
    job_id = _submit(install, install.network, "or-comparison.v3")
    status = job_status(job_id, rt=install.rt, scope=install.presenter)
    assert (status.job_id, status.state) == (job_id, AttemptState.QUEUED)


def test_job_of_an_organization_without_a_network_stays_hidden(install):
    job_id = _submit(install, install.stranger, "or-comparison.v3")
    with pytest.raises(JobNotFound):
        job_status(job_id, rt=install.rt, scope=install.presenter)


def test_own_v2_job_is_unchanged(install):
    job_id = _submit(install, install.presenter, "or-comparison.v2")
    assert job_status(job_id, rt=install.rt, scope=install.presenter).job_id == job_id


def test_only_v1_network_jobs_are_read_across_organizations(install):  # security review
    job_id = _submit(install, install.network, "or-comparison.v2")
    with pytest.raises(JobNotFound):
        job_status(job_id, rt=install.rt, scope=install.presenter)


def test_network_forecast_job_is_visible(install):  # W2-06 lead CR, before W3-F03
    job_id = _submit(install, install.network, "forecast.v1")
    assert job_status(job_id, rt=install.rt, scope=install.presenter).job_id == job_id
