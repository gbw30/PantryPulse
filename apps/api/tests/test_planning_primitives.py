import json
from itertools import product

import pytest
from pydantic import ValidationError

from app.schemas.planning_primitives import (
    AllocationMethod,
    TransferMode,
    TransferModeSelection,
)

MODE_STRINGS = ("HUB_ONLY", "HUB_AND_PANTRY")
METHOD_STRINGS = ("CLASSICAL_GP", "EGP_PI_INSPIRED")


def test_enums_have_exactly_the_contract_values():
    assert sorted(m.value for m in TransferMode) == sorted(MODE_STRINGS)
    assert sorted(m.value for m in AllocationMethod) == sorted(METHOD_STRINGS)


@pytest.mark.parametrize("raw", MODE_STRINGS)
def test_accepts_each_exact_mode_string(raw):
    selection = TransferModeSelection.model_validate({"transfer_mode": raw})
    assert selection.transfer_mode is TransferMode(raw)


@pytest.mark.parametrize("raw", MODE_STRINGS)
def test_accepts_each_exact_mode_string_from_json(raw):
    selection = TransferModeSelection.model_validate_json(json.dumps({"transfer_mode": raw}))
    assert selection.transfer_mode is TransferMode(raw)


@pytest.mark.parametrize("member", list(TransferMode))
def test_accepts_native_enum_members(member):
    assert TransferModeSelection(transfer_mode=member).transfer_mode is member


REJECTED_PAYLOADS = [
    pytest.param({}, id="missing"),
    pytest.param({"transfer_mode": None}, id="null"),
    pytest.param({"transfer_mode": True}, id="true"),
    pytest.param({"transfer_mode": False}, id="false"),
    pytest.param({"transfer_mode": 0}, id="int-zero"),
    pytest.param({"transfer_mode": 1}, id="int-one"),
    pytest.param({"transfer_mode": 1.0}, id="float"),
    pytest.param({"transfer_mode": ["HUB_ONLY"]}, id="list"),
    pytest.param({"transfer_mode": "HUB_AND_DONOR"}, id="unknown"),
    pytest.param({"transfer_mode": ""}, id="empty-string"),
    pytest.param({"transfer_mode": "hub_only"}, id="lowercase"),
    pytest.param({"transfer_mode": "Hub_And_Pantry"}, id="mixed-case"),
    pytest.param({"transfer_mode": " HUB_ONLY"}, id="leading-space"),
    pytest.param({"transfer_mode": "HUB_ONLY "}, id="trailing-space"),
    pytest.param({"transfer_mode": "HUB_ONLY\n"}, id="trailing-newline"),
    pytest.param({"transfer_mode": "HUB_ONLY", "extra": 1}, id="extra-field"),
    pytest.param({"transfer_mode": "HUB_ONLY", "method": "CLASSICAL_GP"}, id="method-is-extra"),
]


@pytest.mark.parametrize("payload", REJECTED_PAYLOADS)
def test_rejects_invalid_payloads(payload):
    with pytest.raises(ValidationError):
        TransferModeSelection.model_validate(payload)


@pytest.mark.parametrize("payload", REJECTED_PAYLOADS)
def test_rejects_invalid_payloads_from_json(payload):
    with pytest.raises(ValidationError):
        TransferModeSelection.model_validate_json(json.dumps(payload))


@pytest.mark.parametrize("payload", [None, True, 3, "HUB_ONLY", ["HUB_ONLY"]])
def test_rejects_non_object_payloads(payload):
    with pytest.raises(ValidationError):
        TransferModeSelection.model_validate(payload)


def test_no_default_when_constructed_without_mode():
    with pytest.raises(ValidationError):
        TransferModeSelection()


def test_all_four_method_mode_combinations_are_independent():
    combos = {
        (AllocationMethod(method), TransferModeSelection(transfer_mode=mode).transfer_mode)
        for method, mode in product(METHOD_STRINGS, MODE_STRINGS)
    }
    assert len(combos) == 4
    assert {(m.value, t.value) for m, t in combos} == set(product(METHOD_STRINGS, MODE_STRINGS))


def test_json_serialization_emits_enum_strings():
    selection = TransferModeSelection(transfer_mode=TransferMode.HUB_AND_PANTRY)
    assert json.loads(selection.model_dump_json()) == {"transfer_mode": "HUB_AND_PANTRY"}
    dumped = selection.model_dump(mode="json")
    assert dumped == {"transfer_mode": "HUB_AND_PANTRY"}
    assert type(dumped["transfer_mode"]) is str


def _resolve(schema, node):
    ref = node.get("$ref")
    if ref is None:
        return node
    name = ref.rsplit("/", 1)[-1]
    return schema["$defs"][name]


def test_json_schema_requires_mode_with_exact_enum_and_no_default_or_null():
    schema = TransferModeSelection.model_json_schema()
    assert schema["required"] == ["transfer_mode"]
    assert schema.get("additionalProperties") is False
    assert set(schema["properties"]) == {"transfer_mode"}

    prop = schema["properties"]["transfer_mode"]
    assert "default" not in prop
    assert "anyOf" not in prop and "oneOf" not in prop

    resolved = _resolve(schema, prop)
    assert "default" not in resolved
    assert sorted(resolved["enum"]) == sorted(MODE_STRINGS)
    assert resolved.get("type") == "string"
    assert None not in resolved["enum"]
    assert "null" not in json.dumps(schema)
