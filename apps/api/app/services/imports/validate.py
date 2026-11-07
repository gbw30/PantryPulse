"""Template row validation, pure and streaming (W1-D02).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from collections.abc import Mapping
from typing import BinaryIO

from app.schemas.v1_envelope import V1_ENVELOPE, Envelope
from app.schemas.v1_imports import ImportSettings, ValidationReport
from app.schemas.v1_networks import TemplateName
from app.services.v1_errors import NotImplementedV1


def validate_files(
    files: Mapping[TemplateName, BinaryIO],
    settings: ImportSettings,
    envelope: Envelope = V1_ENVELOPE,
) -> ValidationReport:
    raise NotImplementedV1("W1-D02")
