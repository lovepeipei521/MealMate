"""Agent tracing primitives.

This module keeps per-request tracing state in ContextVars. A trace may span
multiple agent runs, while a run represents one request handled by one agent.
"""

from __future__ import annotations

import dataclasses
import json
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterator, Optional


def new_trace_id() -> str:
    """Return a globally unique trace identifier."""

    return str(uuid.uuid4())


def new_run_id() -> str:
    """Return a globally unique agent run identifier."""

    return str(uuid.uuid4())


def new_span_id() -> str:
    """Return a globally unique span identifier."""

    return str(uuid.uuid4())


def normalize_trace_id(value: Optional[str]) -> Optional[str]:
    """Return a canonical UUID string when value is a valid trace id."""

    if not value:
        return None
    try:
        return str(uuid.UUID(str(value).strip()))
    except (TypeError, ValueError, AttributeError):
        return None


@dataclass
class TraceRunState:
    """Mutable metrics and trace data for a single agent run."""

    trace_id: str
    run_id: str
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    agent_name: str = "default"
    status: str = "running"
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    ttft_ms: Optional[int] = None
    iteration_count: int = 0
    llm_call_count: int = 0
    tool_call_count: int = 0
    subagent_call_count: int = 0
    tool_failure_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    source: str = "online"
    experiment_id: Optional[str] = None
    dataset_case_id: Optional[str] = None
    repeat_index: Optional[int] = None
    config_hash: Optional[str] = None
    trace: list[dict[str, Any]] = field(default_factory=list)

    def snapshot(self) -> dict[str, Any]:
        """Return a JSON/DB-friendly snapshot without mutating the state."""

        return {
            "trace_id": self.trace_id,
            "run_id": self.run_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "agent_name": self.agent_name,
            "status": self.status,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "duration_ms": self.duration_ms,
            "ttft_ms": self.ttft_ms,
            "iteration_count": self.iteration_count,
            "llm_call_count": self.llm_call_count,
            "tool_call_count": self.tool_call_count,
            "subagent_call_count": self.subagent_call_count,
            "tool_failure_count": self.tool_failure_count,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "source": self.source,
            "experiment_id": self.experiment_id,
            "dataset_case_id": self.dataset_case_id,
            "repeat_index": self.repeat_index,
            "config_hash": self.config_hash,
            "trace": list(self.trace),
        }


_trace_state: ContextVar[Optional[TraceRunState]] = ContextVar(
    "agent_trace_state", default=None
)
_current_span_id: ContextVar[Optional[str]] = ContextVar(
    "agent_current_span_id", default=None
)
_parent_span_id: ContextVar[Optional[str]] = ContextVar(
    "agent_parent_span_id", default=None
)


def _resolve_state(state: Optional[TraceRunState] = None) -> Optional[TraceRunState]:
    return state if state is not None else _trace_state.get()


def create_trace_state(
    *,
    trace_id: Optional[str] = None,
    run_id: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    agent_name: str = "default",
    source: str = "online",
    experiment_id: Optional[str] = None,
    dataset_case_id: Optional[str] = None,
    repeat_index: Optional[int] = None,
    config_hash: Optional[str] = None,
) -> TraceRunState:
    """Create a run state; callers normally push it with set_trace_state()."""

    return TraceRunState(
        trace_id=normalize_trace_id(trace_id) or new_trace_id(),
        run_id=run_id or new_run_id(),
        user_id=user_id,
        session_id=session_id,
        agent_name=agent_name,
        source=source,
        experiment_id=experiment_id,
        dataset_case_id=dataset_case_id,
        repeat_index=repeat_index,
        config_hash=config_hash,
    )


def set_trace_state(state: Optional[TraceRunState]):
    """Set the current run state and return the ContextVar token."""

    return _trace_state.set(state)


def reset_trace_state(token) -> None:
    """Restore the previous run state using a token from set_trace_state()."""

    _trace_state.reset(token)


def get_trace_state() -> Optional[TraceRunState]:
    """Return the current run state, if any."""

    return _trace_state.get()


def get_current_trace_ids(
    state: Optional[TraceRunState] = None,
) -> tuple[Optional[str], Optional[str]]:
    """Return the current trace and business run ids."""

    resolved = _resolve_state(state)
    if not resolved:
        return None, None
    return resolved.trace_id, resolved.run_id


def get_current_span_id() -> Optional[str]:
    """Return the current span id."""

    return _current_span_id.get()


def get_current_parent_span_id() -> Optional[str]:
    """Return the parent of the current span."""

    return _parent_span_id.get()


def set_span_context(
    span_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
):
    """Set the current span and return the tokens needed to restore it."""
    effective_span_id = span_id or new_span_id()
    previous_span_id = _current_span_id.get()
    current_token = _current_span_id.set(effective_span_id)
    effective_parent_id = (
        parent_span_id if parent_span_id is not None else previous_span_id
    )
    parent_token = _parent_span_id.set(effective_parent_id)
    return effective_span_id, (current_token, parent_token)


def reset_span_context(tokens) -> None:
    """Restore the current and parent span context using returned tokens."""
    current_token, parent_token = tokens
    _parent_span_id.reset(parent_token)
    _current_span_id.reset(current_token)


def record_iteration(iteration: int, state: Optional[TraceRunState] = None) -> None:
    resolved = _resolve_state(state)
    if resolved:
        resolved.iteration_count += 1


def record_llm_call(state: Optional[TraceRunState] = None) -> None:
    resolved = _resolve_state(state)
    if resolved:
        resolved.llm_call_count += 1


def record_llm_usage(
    *,
    input_tokens: Optional[int] = None,
    output_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    state: Optional[TraceRunState] = None,
) -> None:
    resolved = _resolve_state(state)
    if not resolved:
        return
    resolved.input_tokens += int(input_tokens or 0)
    resolved.output_tokens += int(output_tokens or 0)
    if total_tokens is None:
        total_tokens = (input_tokens or 0) + (output_tokens or 0)
    resolved.total_tokens += int(total_tokens or 0)


def record_first_token(state: Optional[TraceRunState] = None) -> None:
    resolved = _resolve_state(state)
    if resolved and resolved.ttft_ms is None:
        resolved.ttft_ms = int(
            (datetime.utcnow() - resolved.started_at).total_seconds() * 1000
        )


def record_tool_call(
    name: Optional[str] = None, state: Optional[TraceRunState] = None
) -> None:
    resolved = _resolve_state(state)
    if resolved:
        resolved.tool_call_count += 1


def record_tool_result(success: bool, state: Optional[TraceRunState] = None) -> None:
    resolved = _resolve_state(state)
    if resolved and not success:
        resolved.tool_failure_count += 1


def record_subagent_call(state: Optional[TraceRunState] = None) -> None:
    resolved = _resolve_state(state)
    if resolved:
        resolved.subagent_call_count += 1


def record_trace_step(
    step: dict[str, Any], state: Optional[TraceRunState] = None
) -> None:
    resolved = _resolve_state(state)
    if not resolved:
        return
    try:
        normalized = json.loads(json.dumps(step, default=_json_default))
    except (TypeError, ValueError):
        normalized = {
            "event_type": step.get("event_type", "trace"),
            "serialization_error": True,
        }
    if not normalized.get("timestamp"):
        normalized["timestamp"] = datetime.utcnow().isoformat()
    resolved.trace.append(normalized)


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    return str(value)


def _finish_state(state: TraceRunState, status: str) -> None:
    if state.finished_at is None:
        state.finished_at = datetime.utcnow()
        state.duration_ms = int(
            (state.finished_at - state.started_at).total_seconds() * 1000
        )
    state.status = status
    state.trace.append(
        {
            "event_type": "run",
            "action": "run_end",
            "span_id": state.run_id,
            "run_id": state.run_id,
            "status": status,
            "finished_at": state.finished_at.isoformat(),
            "duration_ms": state.duration_ms,
        }
    )


def set_run_error(
    error: BaseException | str, state: Optional[TraceRunState] = None
) -> None:
    resolved = _resolve_state(state)
    if not resolved:
        return
    if isinstance(error, BaseException):
        resolved.error_type = type(error).__name__
        resolved.error_message = str(error)
    else:
        resolved.error_type = "Error"
        resolved.error_message = error
    _finish_state(resolved, "failed")


def mark_run_succeeded(state: Optional[TraceRunState] = None) -> None:
    resolved = _resolve_state(state)
    if resolved:
        _finish_state(resolved, "succeeded")


def mark_run_cancelled(state: Optional[TraceRunState] = None) -> None:
    resolved = _resolve_state(state)
    if resolved:
        _finish_state(resolved, "cancelled")


def snapshot_trace_state(
    state: Optional[TraceRunState] = None,
) -> Optional[dict[str, Any]]:
    resolved = _resolve_state(state)
    return resolved.snapshot() if resolved else None


@contextmanager
def span_context(
    span_id: Optional[str] = None,
    parent_span_id: Optional[str] = None,
) -> Iterator[str]:
    """Yield an id for a unit of work and restore the previous span on exit."""

    effective_span_id, tokens = set_span_context(span_id, parent_span_id)
    try:
        yield effective_span_id
    finally:
        reset_span_context(tokens)
