# covers: V1-A22
"""W0-08b: v1 job kinds are registered for admission and advertised once a lane builds them."""

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


def test_built_v1_job_kinds_are_advertised_for_execution():
    advertised, _ = REGISTRY.execution_advertisement()
    # All four are built: import/enrichment/routes-google (CR-w1-data-3, CR-w1-data-4) and
    # or-comparison.v3 (CR-w1-solver-4).
    assert set(V1_KINDS) <= set(advertised)
    assert "or-comparison.v2" in advertised


def test_import_and_enrichment_budgets():
    assert operation_budget_s(OperationKind.IMPORT, PRODUCTION_PROFILE) == 300
    assert operation_budget_s(OperationKind.ENRICHMENT, PRODUCTION_PROFILE) == 300
