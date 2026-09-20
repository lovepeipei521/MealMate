# app/agent/tools/common/__init__.py
"""
通用内置 Tool 集合

提供一些常用的内置 Tool。
"""

from app.agent.tools.common.calculator import CalculatorTool
from app.agent.tools.common.datetime import DateTimeTool
from app.agent.tools.common.websearch import WebSearchTool
from app.agent.tools.common.image_generator import ImageGeneratorTool
from app.agent.tools.common.knowledge_base_search import KnowledgeBaseSearchTool
from app.agent.tools.common.deep_research import DeepResearchTool
from app.agent.registry import AgentHub


def register_common_tools():
    """注册所有通用内置工具到 AgentHub。"""
    AgentHub.register_tool(CalculatorTool(), provider="local")
    AgentHub.register_tool(DateTimeTool(), provider="local")
    AgentHub.register_tool(WebSearchTool(), provider="local")
    AgentHub.register_tool(ImageGeneratorTool(), provider="local")
    AgentHub.register_tool(KnowledgeBaseSearchTool(), provider="local")
    AgentHub.register_tool(DeepResearchTool(), provider="local")


__all__ = [
    "CalculatorTool",
    "DateTimeTool",
    "WebSearchTool",
    "ImageGeneratorTool",
    "KnowledgeBaseSearchTool",
    "DeepResearchTool",
    "register_common_tools",
]
