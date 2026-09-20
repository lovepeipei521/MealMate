# =============================================================================
# MealMate NeMo Guardrails Module
# =============================================================================
# 企业级 Prompt 安全防护模块
# 基于 NVIDIA NeMo Guardrails 框架
# =============================================================================

from app.security.guardrails.guard import (
    MealMateGuard,
    GuardResult,
    SecurityCheckResult,
    guard,
    check_input,
    check_output,
)

__all__ = [
    # 类
    "MealMateGuard",
    "GuardResult", 
    "SecurityCheckResult",
    # 全局实例
    "guard",
    # 便捷函数
    "check_input",
    "check_output",
]
