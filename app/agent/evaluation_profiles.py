"""Per-request Agent evaluation profiles.

The profiles are intentionally scoped to evaluation requests. Online user
requests keep the normal application behavior and cannot select a profile.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Literal


EvaluationProfileName = Literal["baseline", "optimized"]


@dataclass(frozen=True)
class AgentEvaluationProfile:
    name: EvaluationProfileName
    description: str
    system_prompt_suffix: str = ""


BASELINE_PROFILE = AgentEvaluationProfile(
    name="baseline",
    description="当前默认 Agent 系统提示词，不附加评测策略。",
)

OPTIMIZED_PROFILE = AgentEvaluationProfile(
    name="optimized",
    description="增加工具路由、上下文约束和失败处理策略的 Agent 提示词。",
    system_prompt_suffix="""

## Agent 执行策略（评测优化版）
请先判断用户的真实意图，再选择完成任务所必需的工具，遵守以下规则：
- 数学运算使用 calculator；当前日期或时间使用 datetime。
- MealMate 内置菜谱、饮食记录和个人知识库问题使用对应的内部工具，不要为了回答这类问题调用 web_search 或 deep_research。
- 需要实时互联网信息时使用 web_search；需要多来源、较完整的专题研究时使用 deep_research。
- 工具调用只传递符合 schema 且与用户问题一致的参数；没有必要时不要重复调用同一个工具。
- 工具返回失败或没有结果时，明确说明当前无法确认的内容，不要编造数据、来源或检索结果，也不要把不相关的工具当作兜底。
- 多轮对话中必须优先遵守历史消息中的过敏、饮食目标和用户明确约束；上下文没有足够信息时直接说明限制。
- 获得工具结果后再组织最终回答，并区分工具事实、推断和不确定信息。
""",
)


PROFILES: dict[EvaluationProfileName, AgentEvaluationProfile] = {
    "baseline": BASELINE_PROFILE,
    "optimized": OPTIMIZED_PROFILE,
}

_current_profile: ContextVar[EvaluationProfileName | None] = ContextVar(
    "mealmate_agent_evaluation_profile", default=None
)


def set_evaluation_profile(
    profile: str | None,
) -> Token[EvaluationProfileName | None]:
    """Set the profile for the current request/task context."""
    if profile is not None and profile not in PROFILES:
        raise ValueError(f"Unsupported Agent evaluation profile: {profile}")
    return _current_profile.set(profile)  # type: ignore[arg-type]


def reset_evaluation_profile(token: Token[EvaluationProfileName | None]) -> None:
    """Restore the profile that was active before the request."""
    _current_profile.reset(token)


def get_evaluation_profile() -> AgentEvaluationProfile | None:
    """Return the profile active for the current request, if any."""
    name = _current_profile.get()
    return PROFILES.get(name) if name else None


def get_evaluation_prompt_suffix() -> str:
    """Return the optional prompt policy for the active evaluation profile."""
    profile = get_evaluation_profile()
    return profile.system_prompt_suffix if profile else ""


__all__ = [
    "AgentEvaluationProfile",
    "EvaluationProfileName",
    "PROFILES",
    "get_evaluation_profile",
    "get_evaluation_prompt_suffix",
    "reset_evaluation_profile",
    "set_evaluation_profile",
]
