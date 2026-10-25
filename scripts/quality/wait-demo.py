"""Wait for actual API health and shared worker admission readiness in CI."""
import os
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps/api"))
from app.services.forecast_runtime import configured_runtime

deadline = time.monotonic() + 45
while time.monotonic() < deadline:
    runtime = configured_runtime()
    try:
        urllib.request.urlopen(os.environ.get("PANTRYPULSE_API_ORIGIN", "http://127.0.0.1:8000") + "/api/v1/health", timeout=2)
        if runtime.queue.control().state.value == "READY":
            print("API and real Linux supervisor ready")
            break
    except Exception:
        time.sleep(0.5)
    finally:
        runtime.engine.dispose()
else:
    raise SystemExit("Connected demo did not become ready")
