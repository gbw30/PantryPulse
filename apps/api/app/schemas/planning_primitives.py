"""Transfer-mode and allocation-method primitives (BACKEND-SPEC.md section 13.1, BE-01).

Reusable types and a required-mode schema fragment only. The enclosing scenario or job
model owns the method field; its public error envelope is OPEN-29.
"""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator


class TransferMode(StrEnum):
    HUB_ONLY = "HUB_ONLY"
    HUB_AND_PANTRY = "HUB_AND_PANTRY"


class AllocationMethod(StrEnum):
    CLASSICAL_GP = "CLASSICAL_GP"
    EGP_PI_INSPIRED = "EGP_PI_INSPIRED"


class TransferModeSelection(BaseModel):
    """Required, explicit transfer mode with no default, coercion or extra fields."""

    # Enum validation matches values exactly; strict mode would also reject exact strings.
    model_config = ConfigDict(extra="forbid", frozen=True)

    transfer_mode: TransferMode

    @field_validator("transfer_mode", mode="before")
    @classmethod
    def _reject_non_str(cls, value: object) -> object:
        # Lax enum validation would decode bytes and accept non-str enums by value;
        # match check_mode_route, which only accepts str or TransferMode values.
        if not isinstance(value, str):
            raise ValueError("transfer_mode must be a string")
        return value
