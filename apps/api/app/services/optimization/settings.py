"""Versioned computational settings shared by offline and application adapters."""

DEFAULT_SEARCH_SECONDS = 120
MAX_SEARCH_SECONDS = 300


def solver_settings(search_seconds=DEFAULT_SEARCH_SECONDS, *, seed=0):
    if type(search_seconds) is not int or not 1 <= search_seconds <= MAX_SEARCH_SECONDS:
        raise ValueError("UNSUPPORTED_SEARCH_BUDGET")
    if type(seed) is not int or not 0 <= seed < 2**31:
        raise ValueError("UNSUPPORTED_SOLVER_SEED")
    method = search_seconds + 30
    return dict(
        version="or-solver-settings-v2",
        workers=1,
        seed=seed,
        search_milliseconds=search_seconds * 1000,
        method_wall_milliseconds=method * 1000,
        comparison_wall_milliseconds=(2 * method + 30) * 1000,
    )


def validate_settings(settings=None):
    if settings is None:
        return solver_settings()
    try:
        milliseconds = settings["search_milliseconds"]
        if type(milliseconds) is not int or milliseconds % 1000:
            raise ValueError("UNSUPPORTED_SOLVER_SETTINGS")
        expected = solver_settings(milliseconds // 1000, seed=settings["seed"])
        if settings != expected or type(settings["workers"]) is not int:
            raise ValueError("UNSUPPORTED_SOLVER_SETTINGS")
    except (KeyError, TypeError) as exc:
        raise ValueError("UNSUPPORTED_SOLVER_SETTINGS") from exc
    return expected


def execution_limits(settings=None):
    value = validate_settings(settings)
    return value["method_wall_milliseconds"] / 1000, value["comparison_wall_milliseconds"] / 1000
