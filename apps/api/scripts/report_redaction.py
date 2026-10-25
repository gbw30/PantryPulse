"""Sanitize configured database credentials from development test failure text."""

import os
from urllib.parse import unquote, urlsplit


def redact_database_credentials(value):
    text = str(value)
    for name in ("DATABASE_URL", "DATABASE_URL_UNPOOLED", "PP19_TEST_DATABASE_URL",
                 "PP_TEST_DATABASE_URL"):
        url = os.environ.get(name, "")
        if not url:
            continue
        text = text.replace(url, "[REDACTED_DATABASE_URL]")
        password = urlsplit(url).password
        if password:
            for secret in (password, unquote(password)):
                text = text.replace(secret, "[REDACTED]")
    return text
