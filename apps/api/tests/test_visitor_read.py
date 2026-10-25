"""Opt-in read-only visitor scope for saved Overview reads (user decision 2026-10-25).

GET reads fall back to PP_VISITOR_ORGANIZATION_ID when no presenter session exists; writes never do.
"""

from uuid import uuid4

import pytest

from app.services.presenter_access import VISITOR_ACTOR, AccessError, read_scope


class NoSessionRequest:
    cookies: dict = {}
    headers: dict = {}
    method = "GET"


def test_reads_without_a_session_use_the_configured_visitor_organization(monkeypatch):
    organization = uuid4()
    monkeypatch.setenv("PP_VISITOR_ORGANIZATION_ID", str(organization))
    scope = read_scope(NoSessionRequest(), runtime=None)
    assert scope.organization_id == organization
    assert scope.actor_ref == VISITOR_ACTOR


def test_reads_without_a_session_stay_401_when_visitor_access_is_off(monkeypatch):
    monkeypatch.delenv("PP_VISITOR_ORGANIZATION_ID", raising=False)
    with pytest.raises(AccessError) as error:
        read_scope(NoSessionRequest(), runtime=None)
    assert (error.value.code, error.value.status) == ("PRESENTER_REQUIRED", 401)


def test_a_malformed_visitor_organization_fails_closed(monkeypatch):
    monkeypatch.setenv("PP_VISITOR_ORGANIZATION_ID", "not-a-uuid")
    with pytest.raises(AccessError) as error:
        read_scope(NoSessionRequest(), runtime=None)
    assert error.value.status == 503


def test_overview_reads_use_the_visitor_scope_and_writes_do_not(monkeypatch):
    from app.routers import dashboard, forecasts

    reads = {
        dashboard.summary: "dashboard summary",
        dashboard.shortages: "shortages",
        forecasts.catalog: "forecast catalog",
    }
    for route, name in reads.items():
        defaults = [p.default for p in __import__("inspect").signature(route).parameters.values()]
        assert any(getattr(d, "dependency", None) is forecasts.reader for d in defaults), name

    # Writes keep the presenter dependency: no session is 401 even with visitor access on.
    monkeypatch.setenv("PP_VISITOR_ORGANIZATION_ID", str(uuid4()))
    write = NoSessionRequest()
    write.method = "POST"
    with pytest.raises(AccessError) as error:
        forecasts.presenter(write, rt=None)
    assert (error.value.code, error.value.status) == ("PRESENTER_REQUIRED", 401)
