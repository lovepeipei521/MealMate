import uuid

from langchain_core.outputs import LLMResult

from app.agent.tracing import (
    create_trace_state,
    get_current_parent_span_id,
    get_current_span_id,
    mark_run_cancelled,
    mark_run_succeeded,
    normalize_trace_id,
    record_iteration,
    record_llm_usage,
    record_subagent_call,
    record_tool_call,
    record_tool_result,
    reset_trace_state,
    set_run_error,
    set_trace_state,
    snapshot_trace_state,
    span_context,
)
from app.llm.callbacks import LLMUsageCallbackHandler
from app.llm.context import get_llm_context, llm_context


def test_trace_id_normalization_and_run_state_transitions():
    trace_id = str(uuid.uuid4()).upper()
    assert normalize_trace_id(trace_id) == trace_id.lower()
    assert normalize_trace_id("not-a-uuid") is None

    state = create_trace_state(trace_id=trace_id, run_id="run-1")
    record_iteration(0, state)
    record_iteration(0, state)
    record_tool_call("calculator", state)
    record_tool_result(False, state)
    record_subagent_call(state)
    record_llm_usage(input_tokens=3, output_tokens=4, state=state)

    snapshot = snapshot_trace_state(state)
    assert snapshot["trace_id"] == trace_id.lower()
    assert snapshot["iteration_count"] == 2
    assert snapshot["tool_call_count"] == 1
    assert snapshot["tool_failure_count"] == 1
    assert snapshot["subagent_call_count"] == 1
    assert snapshot["total_tokens"] == 7

    mark_run_succeeded(state)
    assert snapshot_trace_state(state)["status"] == "succeeded"
    set_run_error("provider failed", state)
    assert snapshot_trace_state(state)["status"] == "failed"

    cancelled = create_trace_state(run_id="run-2")
    mark_run_cancelled(cancelled)
    assert snapshot_trace_state(cancelled)["status"] == "cancelled"


def test_nested_span_context_restores_parent():
    with span_context("agent-root"):
        assert get_current_span_id() == "agent-root"
        assert get_current_parent_span_id() is None
        with span_context("tool-span"):
            assert get_current_span_id() == "tool-span"
            assert get_current_parent_span_id() == "agent-root"
        assert get_current_span_id() == "agent-root"
        assert get_current_parent_span_id() is None
    assert get_current_span_id() is None

    with span_context("tool-span", parent_span_id="llm-span"):
        assert get_current_span_id() == "tool-span"
        assert get_current_parent_span_id() == "llm-span"


def test_nested_llm_context_restores_previous_context():
    assert get_llm_context() is None
    with llm_context(
        "outer", trace_id="trace-a", run_id="run-a", span_id="context-span"
    ):
        outer = get_llm_context()
        with llm_context("inner"):
            inner = get_llm_context()
            assert inner.module_name == "inner"
            assert inner.trace_id == "trace-a"
            assert inner.run_id == "run-a"
            assert inner.parent_span_id == "context-span"
            assert inner.span_id != "context-span"
        assert get_llm_context() is outer
        assert get_llm_context().trace_id == "trace-a"
    assert get_llm_context() is None


def test_llm_callback_keeps_context_by_langchain_run_id(monkeypatch):
    handler = LLMUsageCallbackHandler()
    writes = []
    monkeypatch.setattr(handler, "_schedule_write", writes.append)

    first = create_trace_state(trace_id=str(uuid.uuid4()), run_id="run-a")
    token = set_trace_state(first)
    first_lc_run_id = uuid.uuid4()
    with span_context("span-a"), llm_context(
        "agent:default",
        user_id="user-a",
        conversation_id=str(uuid.uuid4()),
        trace_id=first.trace_id,
        run_id=first.run_id,
        span_id="span-a",
        parent_span_id="agent-root-a",
    ):
        handler.on_llm_start({}, [], run_id=first_lc_run_id)
    reset_trace_state(token)

    second = create_trace_state(trace_id=str(uuid.uuid4()), run_id="run-b")
    token = set_trace_state(second)
    with span_context("span-b"), llm_context(
        "agent:other",
        user_id="user-b",
        trace_id=second.trace_id,
        run_id=second.run_id,
        span_id="span-b",
    ):
        handler.on_llm_end(
            LLMResult(
                generations=[],
                llm_output={
                    "token_usage": {
                        "prompt_tokens": 2,
                        "completion_tokens": 5,
                        "total_tokens": 7,
                    }
                },
            ),
            run_id=first_lc_run_id,
        )
    reset_trace_state(token)

    assert writes[0]["trace_id"] == first.trace_id
    assert writes[0]["run_id"] == "run-a"
    assert writes[0]["span_id"] == "span-a"
    assert writes[0]["parent_span_id"] == "agent-root-a"
    assert writes[0]["user_id"] == "user-a"
    assert first.llm_call_count == 1
    assert first.input_tokens == 2
    assert first.output_tokens == 5
    assert first.total_tokens == 7
    assert second.llm_call_count == 0
