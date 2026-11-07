"""Blank templates, the column guide (W1-D03) and examples (W3-P03).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from typing import Literal

from app.schemas.v1_networks import TemplateCatalog, TemplateName
from app.schemas.v1_planning import NetworkMode
from app.services.v1_errors import NotImplementedV1


def template_catalog(mode: NetworkMode | None) -> TemplateCatalog:
    raise NotImplementedV1("W1-D03")


def template_csv(name: TemplateName, kind: Literal["blank", "example"]) -> str:
    raise NotImplementedV1("W3-P03" if kind == "example" else "W1-D03")
