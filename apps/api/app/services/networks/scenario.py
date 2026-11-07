"""Network → frozen or-input-v3 scenario (W1-D09).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from uuid import UUID

from app.schemas.v1_planning import ORInputV3, ScenarioOptions
from app.services.v1_errors import NotImplementedV1


def build_scenario(
    rt,
    scope,
    network_id: UUID,
    dataset_version_id: UUID,
    forecast_run_id: UUID,
    options: ScenarioOptions,
) -> ORInputV3:
    raise NotImplementedV1("W1-D09")
