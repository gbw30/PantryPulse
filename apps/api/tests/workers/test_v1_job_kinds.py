# covers: V1-A22
"""W0-08b: v1 job kinds are registered for admission, never advertised until a lane builds them."""

from app.services.jobs.contracts import PRODUCTION_PROFILE, OperationKind
from app.services.jobs.policies import operation_budget_s
from app.workers.production import REGISTRY

V1_KINDS = {
    "import.v1": OperationKind.IMPORT,
    "enrichment.v1": OperationKind.ENRICHMENT,
    "routes-google.v1": OperationKind.ENRICHMENT,
    "or-comparison.v3": OperationKind.COMPARISON,
}


def test_v1_job_kinds_registered():
    for contract, kind in V1_KINDS.items():
        assert REGISTRY.get(contract).operation_kind == kind
    assert {"forecast.v1", "or-comparison.v2"} <= set(REGISTRY.contracts())


def test_v1_stub_handlers_are_not_advertised_for_execution():
    advertised, _ = REGISTRY.execution_advertisement()
    built = {"enrichment.v1", "import.v1", "routes-google.v1"}  # CR-w1-data-3, CR-w1-data-4
    assert built <= set(advertised)
    assert not (set(V1_KINDS) - built) & set(advertised)
    assert "or-comparison.v2" in advertised


def test_import_and_enrichment_budgets():
    assert operation_budget_s(OperationKind.IMPORT, PRODUCTION_PROFILE) == 300
    assert operation_budget_s(OperationKind.ENRICHMENT, PRODUCTION_PROFILE) == 300
