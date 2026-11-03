"""Optional strict gate: an unavailable environment must not qualify as a pass."""

import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--require-no-skips",
        action="store_true",
        default=False,
        help="Fail if any test or collection is skipped (for PostgreSQL/Linux qualification).",
    )


def pytest_sessionfinish(session, exitstatus):
    if not session.config.getoption("--require-no-skips"):
        return
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter and reporter.stats.get("skipped") and exitstatus == 0:
        reporter.write_sep("!", "Strict gate failed: skipped checks are NOT RUN")
        session.exitstatus = pytest.ExitCode.TESTS_FAILED
