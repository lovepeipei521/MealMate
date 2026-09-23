from app.agent.agents.base import BaseAgent
from app.agent.types import ToolResultInfo


def make_result(name: str, success: bool) -> ToolResultInfo:
    return ToolResultInfo(
        tool_call_id="call-1",
        name=name,
        success=success,
        result=None if not success else {"ok": True},
        error=None if success else "upstream failure",
    )


def test_web_search_failure_returns_direct_message():
    message = BaseAgent._network_tool_failure_message(
        [make_result("web_search", success=False)]
    )

    assert message == "联网搜索失败，当前无法获取互联网结果，请稍后重试。"
    assert "知识库" not in message


def test_deep_research_failure_returns_direct_message():
    message = BaseAgent._network_tool_failure_message(
        [make_result("deep_research", success=False)]
    )

    assert message == "深度研究失败，当前无法获取互联网结果，请稍后重试。"
    assert "知识库" not in message


def test_successful_network_tool_does_not_trigger_failure_message():
    message = BaseAgent._network_tool_failure_message(
        [make_result("web_search", success=True)]
    )

    assert message is None


def test_non_network_tool_failure_does_not_trigger_failure_message():
    message = BaseAgent._network_tool_failure_message(
        [make_result("calculator", success=False)]
    )

    assert message is None
