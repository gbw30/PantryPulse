"""Step outcome parsing and cutoff-breach recording (WQ-05, spec §9.3)."""

from app.services.jobs.contracts import StepStatus
from app.workers.process_driver import ChildOutput
from app.workers.publication import step_outcome

DONE = ChildOutput(
    stdout=b'{"status":"COMPLETED","output":{"x":1}}', stderr=b"", overflow=False, returncode=0
)
KILLED = ChildOutput(stdout=b"", stderr=b"", overflow=False, returncode=-9)


def test_exit_after_the_hard_cutoff_is_recorded_as_a_breach():
    outcome = step_outcome(
        "primary", KILLED, timed_out=True, overflowed=False, elapsed_s=270.4, hard_stop_s=270
    )
    assert outcome.status is StepStatus.TIMED_OUT
    assert outcome.details["cutoff_breach_s"] == 0.4
    assert outcome.summary()["cutoff_breach_s"] == 0.4


def test_exit_within_the_cutoff_records_no_breach():
    outcome = step_outcome(
        "primary", KILLED, timed_out=True, overflowed=False, elapsed_s=269.8, hard_stop_s=270
    )
    assert "cutoff_breach_s" not in outcome.details
    assert "cutoff_breach_s" not in outcome.summary()


def test_late_completion_past_the_cutoff_is_not_publishable():
    outcome = step_outcome(
        "primary", DONE, timed_out=False, overflowed=False, elapsed_s=271, hard_stop_s=270
    )
    assert outcome.status is StepStatus.TIMED_OUT
    assert outcome.details["cutoff_breach_s"] == 1


def test_malformed_and_non_object_output_are_classified():
    bad = ChildOutput(stdout=b"[1]", stderr=b"", overflow=False, returncode=0)
    assert (
        step_outcome(
            "s", bad, timed_out=False, overflowed=False, elapsed_s=1, hard_stop_s=5
        ).error_code
        == "CHILD_EXITED_ABNORMALLY"
    )
    odd = ChildOutput(
        stdout=b'{"status":"FAILED","error_code":"lower"}', stderr=b"", overflow=False, returncode=0
    )
    assert (
        step_outcome(
            "s", odd, timed_out=False, overflowed=False, elapsed_s=1, hard_stop_s=5
        ).error_code
        == "OUTPUT_INVALID"
    )


def test_a_late_programming_error_keeps_its_code_and_stays_ineligible():  # WQ-T16
    err = ChildOutput(
        stdout=b'{"status":"FAILED","error_code":"HANDLER_FAILED","fallback_eligible":false}',
        stderr=b"",
        overflow=False,
        returncode=0,
    )
    outcome = step_outcome(
        "primary", err, timed_out=False, overflowed=False, elapsed_s=270.02, hard_stop_s=270
    )
    assert outcome.status is StepStatus.FAILED
    assert outcome.error_code == "HANDLER_FAILED"
    assert outcome.fallback_eligible is False
    assert outcome.details["cutoff_breach_s"] == 0.02
