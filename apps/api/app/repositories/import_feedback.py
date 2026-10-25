"""Bounded import diagnostics without submitted values or database exception text."""

from contextlib import contextmanager

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.services.inventory.stock import StockError


def feedback(total, errors):
    return dict(atomic=True, accepted_count="0", rejected_count=str(total), errors=errors)


def validation_feedback(errors, total):
    fields = []
    for error in errors[:100]:
        location = tuple(error["loc"])
        if "rows" in location:
            offset = location.index("rows") + 1
            index = (
                location[offset]
                if len(location) > offset and isinstance(location[offset], int)
                else None
            )
            names = location[offset + 1 :] if index is not None else ()
        else:
            index, names = None, tuple(x for x in location if x != "body")
        fields.append(
            dict(row_index=index, field=".".join(map(str, names)) or "row", code=error["type"])
        )
    return feedback(total, fields)


class ImportRejected(StockError):
    def __init__(self, code, status, details):
        super().__init__(code, status)
        self.details = details


@contextmanager
def imported_row(index, total):
    try:
        yield
    except StockError as exc:
        raise ImportRejected(
            exc.code,
            exc.status,
            feedback(total, [dict(row_index=index, field="row", code=exc.code)]),
        ) from None
    except ValidationError as exc:
        errors = [
            dict(
                row_index=index,
                field=".".join(map(str, error["loc"])) or "quantities",
                code=error["type"],
            )
            for error in exc.errors()[:100]
        ]
        raise ImportRejected("INVALID_OPERATIONAL_INPUT", 422, feedback(total, errors)) from None
    except IntegrityError:
        raise ImportRejected(
            "OPERATIONAL_CONFLICT",
            409,
            feedback(total, [dict(row_index=index, field="row", code="OPERATIONAL_CONFLICT")]),
        ) from None
