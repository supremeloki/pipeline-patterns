import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest

from pipeline_patterns import (
    FallbackStage,
    Pipeline,
    PipelineAbortedError,
    PipelineError,
    RetryStage,
    StageFailedError,
    StageResult,
    stage,
)


def test_basic_chain_executes_in_order():
    pipe = Pipeline([
        stage("double", lambda n: n * 2),
        stage("increment", lambda n: n + 1),
    ])
    assert pipe.final_value(5) == 11
    assert pipe.stage_names == ("double", "increment")


def test_trace_records_each_stage():
    pipe = Pipeline([stage("a", lambda x: x), stage("b", lambda x: x)])
    trace = pipe.run("v")
    assert len(trace) == 2
    assert all(not t.aborted for t in trace)


def test_stage_failure_wraps_original_error():
    def boom(_):
        raise ValueError("inner")

    pipe = Pipeline([stage("exploder", boom)])
    with pytest.raises(StageFailedError) as excinfo:
        pipe.run(1)
    assert isinstance(excinfo.value.cause, ValueError)
    assert excinfo.value.stage == "exploder"


def test_duplicate_stage_names_rejected():
    with pytest.raises(PipelineError, match="duplicate"):
        Pipeline([stage("x", lambda v: v), stage("x", lambda v: v)])


def test_abort_stops_remaining_stages():
    def stop_if_zero(n):
        if n == 0:
            raise PipelineAbortedError()
        return n

    pipe = Pipeline([
        stage("guard", stop_if_zero),
        stage("never", lambda n: n / 0),
    ])
    trace = pipe.run(0)
    assert len(trace) == 1
    assert trace[0].aborted


def test_stage_can_emit_stage_result_with_metadata():
    def annotated(n):
        return StageResult(value=n * 10, metadata={"multiplier": 10})

    trace = Pipeline([stage("ann", annotated)]).run(2)
    assert trace[0].value == 20
    assert trace[0].metadata["multiplier"] == 10


def test_retry_succeeds_after_transient_failures():
    attempts = {"count": 0}

    def flaky(n):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("transient")
        return n

    wrapped = RetryStage(stage("flaky", flaky), attempts=5)
    assert wrapped.execute("ok") == "ok"
    assert attempts["count"] == 3


def test_retry_exhaustion_raises_stage_failed():
    always = RetryStage(stage("always_bad", lambda _: 1 // 0), attempts=2)
    with pytest.raises(StageFailedError):
        always.execute(0)


def test_fallback_returns_default_on_failure():
    guarded = FallbackStage(stage("bad", lambda _: 1 / 0), fallback_value="safe")
    assert guarded.execute(None) == "safe"


def test_fallback_does_not_swallow_abort():
    aborting = FallbackStage(
        stage("aborter", lambda _: (_ for _ in ()).throw(PipelineAbortedError())),
        fallback_value="nope",
    )
    with pytest.raises(PipelineAbortedError):
        aborting.execute(None)


def test_retry_rejects_invalid_attempts():
    with pytest.raises(PipelineError):
        RetryStage(stage("s", lambda v: v), attempts=0)
