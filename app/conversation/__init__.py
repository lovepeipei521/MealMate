# app/conversation/__init__.py
"""
Conversation module for CookHero.
Handles conversation flow, intent detection, query rewriting, and LLM orchestration.

This module provides a unified interface for all conversation-related functionality,
including context management (re-exported from app.context for convenience).
"""

from app.conversation.intent import IntentDetectionResult, IntentDetector, QueryIntent
from app.conversation.llm_orchestrator import LLMOrchestrator
from app.conversation.query_rewriter import QueryRewriter
from app.database.conversation_repository import conversation_repository
from app.conversation.types import ChatContext, ExtraOptions, UnifiedSource
from app.conversation.prompts import SYSTEM_PROMPT

# Re-export context module for convenience
from app.context import ContextManager, ContextCompressor

__all__ = [
    # Types
    "ChatContext",
    "ExtraOptions",
    "UnifiedSource",
    # Intent detection
    "IntentDetectionResult",
    "IntentDetector",
    "QueryIntent",
    # LLM and query
    "LLMOrchestrator",
    "QueryRewriter",
    # Prompts
    "SYSTEM_PROMPT",
    # Repository
    "conversation_repository",
    # Context management (re-exported from app.context)
    "ContextManager",
    "ContextCompressor",
]
