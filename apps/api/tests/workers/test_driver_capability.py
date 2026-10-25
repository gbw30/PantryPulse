"""Containment capability is reported truthfully on every host (ADR 0005 A2)."""

import sys

from app.workers.process_driver import PosixProcessDriver, linux_containment_available


def test_capability_matches_the_platform():
    expected = sys.platform.startswith("linux")
    assert linux_containment_available() is expected
    assert PosixProcessDriver(cwd=".").capable is expected


def test_unavailable_driver_refuses_to_start_children():
    if linux_containment_available():
        return
    driver = PosixProcessDriver(cwd=".")
    try:
        driver.start([sys.executable, "-c", "pass"], b"", max_stdout_bytes=10)
    except RuntimeError as exc:
        assert "containment" in str(exc)
    else:
        raise AssertionError("an incapable driver must not start children")
