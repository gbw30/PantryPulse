"""Ephemeral CI-only presenter credentials; output is consumed by GITHUB_ENV."""
import hashlib
import json
import secrets
import sys

demo = json.load(open(sys.argv[1], encoding="utf-8"))
password = secrets.token_urlsafe(24)
salt = secrets.token_bytes(16)
digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=64).hex()
values = dict(PP_PRESENTER_USERNAME="ci-presenter", PP_E2E_USERNAME="ci-presenter",
    PP_E2E_PASSWORD=password, PP_PRESENTER_ORGANIZATION_ID=demo["organization_id"],
    PP_PRESENTER_PASSWORD_HASH=f"scrypt$16384$8$1${salt.hex()}${digest}",
    PP_TRUSTED_PROXY_TOKEN=secrets.token_urlsafe(32))
for key, value in values.items():
    print(f"{key}={value}")
