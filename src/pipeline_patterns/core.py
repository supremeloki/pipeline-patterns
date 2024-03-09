from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generic, Protocol, TypeVar

InputT = TypeVar("InputT")
OutputT = TypeVar("OutputT")
NewOutputT = TypeVar("NewOutputT")


class PipelineError(Exception):
    pass


class StageFailedError(PipelineError):
    def __init__(self, stage: str, cause: Exception) -> None:
        super().__init__(f"stage {stage!r} failed: {cause}")
        self.stage = stage
        self.cause = cause


class PipelineAbortedError(PipelineError):
    pass


class Stage(Protocol[InputT, OutputT]):
    name: str

    def execute(self, payload: InputT) -> OutputT: ...


@dataclass(frozen=True)
class StageResult(Generic[OutputT]):
    value: OutputT | None = None
    aborted: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class CallableStage:
    def __init__(self, name: str, func: Callable[[Any], Any]) -> None:
        self.name = name
        self._func = func

    def execute(self, payload: Any) -> Any:
        return self._func(payload)


def stage(name: str, func: Callable[[InputT], OutputT]) -> CallableStage:
    return CallableStage(name, func)


class Pipeline:
    def __init__(self, stages: list[Stage[Any, Any]] | None = None) -> None:
        if stages is None:
            stages = []
        names = [s.name for s in stages]
        if len(names) != len(set(names)):
            raise PipelineError(f"duplicate stage names: {names}")
        self._stages = stages

    @property
    def stage_names(self) -> tuple[str, ...]:
        return tuple(s.name for s in self._stages)

    def run(self, initial: Any) -> list[StageResult[Any]]:
        trace: list[StageResult[Any]] = []
        payload: Any = initial
        for current in self._stages:
            try:
                output = current.execute(payload)
            except PipelineAbortedError:
                trace.append(StageResult(value=None, aborted=True))
                break
            except Exception as exc:
                raise StageFailedError(current.name, exc) from exc
            if isinstance(output, StageResult):
                trace.append(output)
                if output.aborted:
                    break
                payload = output.value
            else:
                trace.append(StageResult(value=output))
                payload = output
        return trace

    def final_value(self, initial: Any) -> Any:
        trace = self.run(initial)
        if not trace:
            return initial
        last = trace[-1]
        if last.aborted:
            raise PipelineAbortedError(f"aborted at {self.stage_names[len(trace) - 1]!r}")
        return last.value


class RetryStage:
    def __init__(self, wrapped: Stage[InputT, OutputT], attempts: int = 3) -> None:
        if attempts < 1:
            raise PipelineError("attempts must be >= 1")
        self.name = f"retry({wrapped.name}, {attempts})"
        self._wrapped = wrapped
        self._attempts = attempts

    def execute(self, payload: InputT) -> OutputT:
        last_error: Exception | None = None
        for _ in range(self._attempts):
            try:
                return self._wrapped.execute(payload)
            except PipelineAbortedError:
                raise
            except Exception as exc:
                last_error = exc
        assert last_error is not None
        raise StageFailedError(self._wrapped.name, last_error)


class FallbackStage:
    def __init__(self, primary: Stage[InputT, OutputT], fallback_value: OutputT) -> None:
        self.name = f"fallback({primary.name})"
        self._primary = primary
        self._fallback = fallback_value

    def execute(self, payload: InputT) -> OutputT:
        try:
            return self._primary.execute(payload)
        except PipelineAbortedError:
            raise
        except Exception:
            return self._fallback
