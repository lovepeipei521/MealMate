"""
Security Check Utilities

统一的安全检查辅助函数，可以在需要安全检查的 endpoint 中使用。
替代在 agent.py 和 conversation.py 中重复的安全检查逻辑。
"""

import logging

from fastapi import HTTPException, Request

from app.security.prompt_guard import prompt_guard, ThreatLevel
from app.security.guardrails import guard as nemo_guard, GuardResult
from app.security.audit import audit_logger

logger = logging.getLogger(__name__)


async def check_message_security(message: str, request: Request) -> str:
    """
    统一的消息安全检查函数。

    执行：
    1. 基础模式检查（prompt_guard）
    2. 深度 LLM 检查（nemo_guard，如果启用）

    Args:
        message: 需要检查的消息内容
        request: FastAPI 请求对象

    Returns:
        str: 清理后的消息（如果检查通过）

    Raises:
        HTTPException: 如果检测到威胁
    """
    # ==========================================================================
    # Security Layer 1: Basic Pattern-based Check (Fast, No LLM)
    # ==========================================================================
    scan_result = prompt_guard.scan(message)
    if scan_result.threat_level == ThreatLevel.BLOCKED:
        # Log security event
        audit_logger.prompt_injection_blocked(
            user_id=getattr(request.state, "user_id", None),
            request=request,
            patterns=scan_result.matched_patterns,
            input_preview=message[:100],
        )
        raise HTTPException(
            status_code=400,
            detail=scan_result.reason or "检测到潜在的恶意输入，请修改您的问题",
        )

    # ==========================================================================
    # Security Layer 2: NeMo Guardrails Deep Check (LLM-based, if enabled)
    # ==========================================================================
    try:
        guard_result = await nemo_guard.check_input(message)
        if guard_result.should_block:
            # Log security event
            audit_logger.prompt_injection_blocked(
                user_id=getattr(request.state, "user_id", None),
                request=request,
                patterns=[
                    "guardrails:"
                    + (guard_result.details or {}).get("threat_type", "unknown")
                ],
                input_preview=message[:100],
            )
            raise HTTPException(
                status_code=400,
                detail=guard_result.reason or "检测到潜在的恶意输入，请修改您的问题",
            )
        elif guard_result.result == GuardResult.WARNING:
            # Log warning but allow through
            logger.warning(f"Guardrails warning: {guard_result.reason}")
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        # Don't block on guardrails errors, just log
        logger.error(f"Guardrails check error (non-blocking): {e}")

    # Return sanitized message if available
    return scan_result.sanitized_input or message
