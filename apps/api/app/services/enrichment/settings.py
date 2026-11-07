"""Local settings; the Google key is stored only locally and never read back (W1-D08).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from pydantic import SecretStr

from app.schemas.v1_enrichment import LocalSettings
from app.services.v1_errors import NotImplementedV1


def get_settings(rt) -> LocalSettings:
    raise NotImplementedV1("W1-D08")


def set_google_key(rt, key: SecretStr) -> LocalSettings:
    raise NotImplementedV1("W1-D08")


def delete_google_key(rt) -> LocalSettings:
    raise NotImplementedV1("W1-D08")
