"""Pure method worker entry. No database writes, source reads or provider execution."""

import time
from fractions import Fraction

import ortools
from ortools.sat.python import cp_model

from app.schemas.or_inputs import ORScenarioPayload, Rational
from app.schemas.or_outputs import MethodOutcome
from app.schemas.planning_primitives import AllocationMethod
from app.services.optimization.candidates import prepare_problem
from app.services.optimization.canonical import operational_hash
from app.services.optimization.classical_gp import attach_classical
from app.services.optimization.constraints import build_physical_model
from app.services.optimization.egp_pi_inspired import attach_research
from app.services.optimization.extract import read_candidate
from app.services.optimization.numerics import audit_model
from app.services.optimization.settings import solver_settings, validate_settings
from app.services.optimization.verify import verify

DEFAULT_SETTINGS = solver_settings()


def solve_one(snapshot, method, settings=None) -> MethodOutcome:
    started = time.monotonic()
    snapshot = ORScenarioPayload.model_validate(snapshot.model_dump())
    method = AllocationMethod(method)
    settings = validate_settings(settings)
    identity = dict(
        method=method,
        transfer_mode=snapshot.transfer_mode,
        operational_hash=snapshot.operational_hash,
        policy_hash=snapshot.policy_hash,
        settings_hash=operational_hash(settings),
        decision_ids=snapshot.decision_ids,
        historical=snapshot.intent == "HISTORICAL_REPLAY",
        solver_version=ortools.__version__,
    )
    problem = prepare_problem(snapshot)
    physical = build_physical_model(problem)
    handles = (
        attach_classical(physical)
        if method == AllocationMethod.CLASSICAL_GP
        else attach_research(physical)
    )
    audit_model(physical.model)  # rejects unsafe emitted activities before native search
    solver = cp_model.CpSolver()
    solver.parameters.num_workers = settings["workers"]
    solver.parameters.random_seed = settings["seed"]
    solver.parameters.max_time_in_seconds = settings["search_milliseconds"] / 1000
    search_start = time.monotonic()
    status = solver.status_name(solver.solve(physical.model))
    search_seconds = time.monotonic() - search_start
    candidate = read_candidate(status, solver, physical)
    common = dict(
        **identity,
        native_status=status,
        physical_fingerprint=physical.fingerprint,
        search_seconds=search_seconds,
        total_seconds=time.monotonic() - started,
    )
    if candidate is None:
        return MethodOutcome(
            **common,
            outcome="FAILED",
            candidate=None,
            verification=None,
            objective=None,
            error_code=f"MODEL_{status}",
        )
    checked = verify(problem, candidate, method)
    if not checked.passed:
        return MethodOutcome(
            **common,
            outcome="FAILED",
            candidate=None,
            verification=checked,
            objective=None,
            error_code="CANDIDATE_VERIFICATION_FAILED",
        )
    metrics = checked.metrics
    expected = (
        metrics.classical_objective
        if method == AllocationMethod.CLASSICAL_GP
        else metrics.research_objective
    )
    native_integer = sum(
        c * solver.value(v) for c, v in zip(handles.coefficients, handles.terms, strict=True)
    )
    if Fraction(native_integer) * handles.scale != expected.fraction():
        raise ValueError("NATIVE_OBJECTIVE_REPLAY_MISMATCH")
    for goal in metrics.goals:
        key = goal.site_id, goal.product_id
        if not goal.target:
            continue
        q_expected = goal.q0 if method == AllocationMethod.CLASSICAL_GP else goal.q
        if solver.value(handles.auxiliaries["q"][key]) != q_expected:
            raise ValueError("NATIVE_DEFICIT_REPLAY_MISMATCH")
        if method == AllocationMethod.EGP_PI_INSPIRED:
            if (
                bool(solver.value(handles.auxiliaries["ap"][key])) != goal.ap
                or bool(solver.value(handles.auxiliaries["rp"][key])) != goal.rp
            ):
                raise ValueError("NATIVE_FLAG_REPLAY_MISMATCH")
    common["total_seconds"] = time.monotonic() - started
    native_bound = solver.best_objective_bound * float(handles.scale)
    return MethodOutcome(
        **common,
        outcome="VERIFIED",
        candidate=candidate,
        verification=checked,
        objective=expected,
        objective_integer=native_integer,
        objective_scale=Rational.of(handles.scale),
        native_bound=native_bound,
        gap=max(
            0, (float(expected.fraction()) - native_bound) / max(1, abs(float(expected.fraction())))
        ),
        warnings=metrics.warnings,
    )
