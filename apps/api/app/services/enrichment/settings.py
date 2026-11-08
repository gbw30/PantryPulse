"""Local settings; the Google key is stored only locally and never read back (W1-D08).

The key lives in local_secrets on this install's database. The API only says whether one is
configured; the routes-google.v1 step child receives it in its environment at spawn."""

import sqlalchemy as sa
from pydantic import SecretStr

from app.schemas.v1_enrichment import LocalSettings

GOOGLE_KEY = "google_maps_api_key"


def google_key_saved(conn: sa.Connection) -> bool:
    return bool(conn.scalar(sa.text("SELECT 1 FROM local_secrets WHERE name = :n"),
                            {"n": GOOGLE_KEY}))


def get_settings(rt) -> LocalSettings:
    with rt.engine.connect() as conn:
        return LocalSettings(google_maps_configured=google_key_saved(conn))


def set_google_key(rt, key: SecretStr) -> LocalSettings:
    with rt.engine.begin() as conn:
        conn.execute(sa.text(
            "INSERT INTO local_secrets (name, value) VALUES (:n, :v) ON CONFLICT (name) DO "
            "UPDATE SET value = excluded.value, updated_at = clock_timestamp()"),
            {"n": GOOGLE_KEY, "v": key.get_secret_value()})
    return LocalSettings(google_maps_configured=True)


def delete_google_key(rt) -> LocalSettings:
    with rt.engine.begin() as conn:
        conn.execute(sa.text("DELETE FROM local_secrets WHERE name = :n"), {"n": GOOGLE_KEY})
    return LocalSettings(google_maps_configured=False)
