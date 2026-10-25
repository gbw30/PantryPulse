from scripts.report_redaction import redact_database_credentials


def test_reports_redact_raw_and_url_encoded_connection_passwords(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:private%40test@localhost/test")
    result = redact_database_credentials(
        "postgresql://user:private%40test@localhost/test password=private@test private%40test")
    assert "private" not in result
    assert "[REDACTED_DATABASE_URL]" in result
