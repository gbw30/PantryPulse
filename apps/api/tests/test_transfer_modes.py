"""BE-02 (BACKEND-SPEC.md section 13.2): mode-dependent route eligibility predicate.

Expected values are written out by hand from the section 13.2 table, not derived from
the implementation.
"""

from uuid import UUID

import pytest

from app.schemas.planning_primitives import AllocationMethod, TransferMode
from app.services.transfer_modes import SiteRole, check_mode_route

HUB_A = UUID("00000000-0000-4000-8000-0000000000a1")
SITE_B = UUID("00000000-0000-4000-8000-0000000000b2")
SITE_C = UUID("00000000-0000-4000-8000-0000000000c3")

ALLOWED = "MODE_ROUTE_ALLOWED"
SELF = "SELF_TRANSFER"
DISABLED = "ROUTE_DISABLED"
DEST = "DESTINATION_NOT_BENEFICIARY"
ORIGIN = "ORIGIN_NOT_ALLOWED_BY_MODE"

# (mode, source_role, destination_role) -> (allowed, reason), distinct IDs, enabled route.
TRUTH_TABLE = [
    ("HUB_ONLY", "HUB", "BENEFICIARY", True, ALLOWED),
    ("HUB_ONLY", "HUB", "HUB", False, DEST),
    ("HUB_ONLY", "BENEFICIARY", "BENEFICIARY", False, ORIGIN),
    ("HUB_ONLY", "BENEFICIARY", "HUB", False, DEST),
    ("HUB_AND_PANTRY", "HUB", "BENEFICIARY", True, ALLOWED),
    ("HUB_AND_PANTRY", "HUB", "HUB", False, DEST),
    ("HUB_AND_PANTRY", "BENEFICIARY", "BENEFICIARY", True, ALLOWED),
    ("HUB_AND_PANTRY", "BENEFICIARY", "HUB", False, DEST),
]


def _call(
    mode="HUB_AND_PANTRY",
    source_id=HUB_A,
    source_role="HUB",
    destination_id=SITE_B,
    destination_role="BENEFICIARY",
    route_enabled=True,
):
    return check_mode_route(
        mode, source_id, source_role, destination_id, destination_role, route_enabled
    )


def test_role_enum_has_exactly_two_values():
    assert sorted(r.value for r in SiteRole) == ["BENEFICIARY", "HUB"]


def test_truth_table_covers_all_eight_combinations():
    combos = {(m, s, d) for m, s, d, _, _ in TRUTH_TABLE}
    assert len(combos) == 8


@pytest.mark.parametrize(("mode", "src", "dst", "allowed", "reason"), TRUTH_TABLE)
def test_truth_table_with_exact_strings(mode, src, dst, allowed, reason):
    decision = _call(mode=mode, source_role=src, destination_role=dst)
    assert decision.allowed is allowed
    assert decision.reason == reason


@pytest.mark.parametrize(("mode", "src", "dst", "allowed", "reason"), TRUTH_TABLE)
def test_truth_table_with_enum_members(mode, src, dst, allowed, reason):
    decision = _call(
        mode=TransferMode(mode), source_role=SiteRole(src), destination_role=SiteRole(dst)
    )
    assert decision.allowed is allowed
    assert decision.reason == reason


def test_self_transfer_rejected_by_value_equality_not_identity():
    same_a = UUID(str(SITE_C))
    same_b = UUID(str(SITE_C))
    assert same_a is not same_b
    decision = _call(source_id=same_a, destination_id=same_b, source_role="BENEFICIARY")
    assert decision.allowed is False
    assert decision.reason == SELF


@pytest.mark.parametrize("mode", ["HUB_ONLY", "HUB_AND_PANTRY"])
def test_disabled_route_rejected_even_for_otherwise_allowed_hub_route(mode):
    decision = _call(mode=mode, route_enabled=False)
    assert decision.allowed is False
    assert decision.reason == DISABLED


def test_beneficiary_origin_with_disabled_route_reports_disabled_in_pantry_mode():
    decision = _call(source_role="BENEFICIARY", route_enabled=False)
    assert (decision.allowed, decision.reason) == (False, DISABLED)


# Overlapping failures: the first failing check in table order wins.
PRECEDENCE = [
    # self + disabled + hub destination + beneficiary origin in HUB_ONLY -> SELF_TRANSFER
    (
        dict(
            mode="HUB_ONLY",
            source_id=SITE_C,
            destination_id=SITE_C,
            source_role="BENEFICIARY",
            destination_role="HUB",
            route_enabled=False,
        ),
        SELF,
    ),
    # self + disabled
    (dict(source_id=SITE_C, destination_id=SITE_C, route_enabled=False), SELF),
    # self + hub destination
    (dict(source_id=HUB_A, destination_id=HUB_A, destination_role="HUB"), SELF),
    # self on an otherwise allowed HUB_ONLY hub->beneficiary shape
    (dict(mode="HUB_ONLY", source_id=HUB_A, destination_id=HUB_A), SELF),
    # disabled + hub destination + beneficiary origin in HUB_ONLY -> ROUTE_DISABLED
    (
        dict(
            mode="HUB_ONLY", source_role="BENEFICIARY", destination_role="HUB", route_enabled=False
        ),
        DISABLED,
    ),
    # disabled + beneficiary origin in HUB_ONLY
    (dict(mode="HUB_ONLY", source_role="BENEFICIARY", route_enabled=False), DISABLED),
    # hub destination + beneficiary origin in HUB_ONLY -> DESTINATION_NOT_BENEFICIARY
    (dict(mode="HUB_ONLY", source_role="BENEFICIARY", destination_role="HUB"), DEST),
]


@pytest.mark.parametrize(("kwargs", "reason"), PRECEDENCE)
def test_overlapping_failure_precedence(kwargs, reason):
    decision = _call(**kwargs)
    assert decision.allowed is False
    assert decision.reason == reason


def test_reason_strings_are_exact():
    reasons = {
        _call().reason,
        _call(source_id=HUB_A, destination_id=HUB_A).reason,
        _call(route_enabled=False).reason,
        _call(destination_role="HUB").reason,
        _call(mode="HUB_ONLY", source_role="BENEFICIARY").reason,
    }
    assert reasons == {ALLOWED, SELF, DISABLED, DEST, ORIGIN}
    for reason in reasons:
        assert isinstance(reason, str)


def test_decision_is_immutable():
    decision = _call()
    with pytest.raises(AttributeError):
        decision.allowed = False  # type: ignore[misc]
    with pytest.raises(AttributeError):
        decision.reason = SELF  # type: ignore[misc]
    assert decision.allowed is True
    assert decision.reason == ALLOWED


def test_decisions_are_deterministic_and_equal_for_equal_inputs():
    assert _call() == _call()
    assert hash(_call()) == hash(_call())


def test_inputs_unchanged():
    args = ["HUB_ONLY", HUB_A, "HUB", SITE_B, "BENEFICIARY", True]
    snapshot = list(args)
    snapshot_ids = (HUB_A.int, SITE_B.int)
    check_mode_route(*args)
    assert args == snapshot
    assert (HUB_A.int, SITE_B.int) == snapshot_ids


# ---- Validation: TypeError for wrong Python types, ValueError for unknown strings ----

NOT_UUID = [str(HUB_A), HUB_A.int, HUB_A.bytes, None, 1.0, True]


@pytest.mark.parametrize("bad", NOT_UUID)
def test_non_uuid_source_id_raises_type_error(bad):
    with pytest.raises(TypeError):
        _call(source_id=bad)


@pytest.mark.parametrize("bad", NOT_UUID)
def test_non_uuid_destination_id_raises_type_error(bad):
    with pytest.raises(TypeError):
        _call(destination_id=bad)


@pytest.mark.parametrize("bad", [1, 0, "true", "True", None, 1.0, [True]])
def test_non_bool_route_enabled_raises_type_error(bad):
    with pytest.raises(TypeError):
        _call(route_enabled=bad)


@pytest.mark.parametrize("bad", [None, 0, 1, b"HUB_ONLY", ["HUB_ONLY"], True])
def test_non_string_mode_raises_type_error(bad):
    with pytest.raises(TypeError):
        _call(mode=bad)


@pytest.mark.parametrize("field", ["source_role", "destination_role"])
@pytest.mark.parametrize("bad", [None, 0, b"HUB", ["HUB"], True])
def test_non_string_role_raises_type_error(field, bad):
    with pytest.raises(TypeError):
        _call(**{field: bad})


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "hub_only",
        "Hub_Only",
        " HUB_ONLY",
        "HUB_ONLY ",
        "HUB",
        "PANTRY",
        "BENEFICIARY",
        "CLASSICAL_GP",
        AllocationMethod.CLASSICAL_GP,
        SiteRole.HUB,
    ],
)
def test_unknown_mode_string_raises_value_error(bad):
    with pytest.raises(ValueError):
        _call(mode=bad)


@pytest.mark.parametrize("field", ["source_role", "destination_role"])
@pytest.mark.parametrize(
    "bad",
    [
        "",
        "hub",
        "Hub",
        "beneficiary",
        " HUB",
        "HUB ",
        "PANTRY",
        "SUPPLIER",
        "HUB_ONLY",
        TransferMode.HUB_ONLY,
    ],
)
def test_unknown_role_string_raises_value_error(field, bad):
    with pytest.raises(ValueError):
        _call(**{field: bad})


def test_invalid_inputs_fail_validation_even_when_self_transfer_would_short_circuit():
    with pytest.raises(ValueError):
        _call(source_id=SITE_C, destination_id=SITE_C, destination_role="pantry")
    with pytest.raises(TypeError):
        _call(source_id=SITE_C, destination_id=SITE_C, route_enabled=1)
    with pytest.raises(ValueError):
        _call(mode="hub_only", source_id=SITE_C, destination_id=SITE_C)


def test_invalid_inputs_fail_validation_even_when_route_disabled_would_short_circuit():
    with pytest.raises(ValueError):
        _call(route_enabled=False, source_role="SUPPLIER")
    with pytest.raises(TypeError):
        _call(route_enabled=False, destination_id=str(SITE_B))


def test_value_error_for_unknown_strings():
    with pytest.raises(ValueError):
        _call(mode="HUB_ONLY ")
