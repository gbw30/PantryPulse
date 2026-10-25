"""Never include configured database credentials in pytest failure reports."""

import pytest

from scripts.report_redaction import redact_database_credentials


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.failed:
        report.longrepr = redact_database_credentials(report.longrepr)
        report.sections = [(name, redact_database_credentials(content))
                           for name, content in report.sections]
