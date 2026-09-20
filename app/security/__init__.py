"""
Security module for CookHero.

Provides enterprise-grade security features:
- Prompt injection protection (basic pattern matching)
- NeMo Guardrails integration (LLM-based deep protection)
- Sensitive data sanitization
- Audit logging
"""

from app.security.prompt_guard import PromptGuard, prompt_guard
from app.security.sanitizer import Sanitizer, sanitizer
from app.security.audit import AuditLogger, audit_logger

# NeMo Guardrails integration
from app.security.guardrails import (
    CookHeroGuard,
    GuardResult,
    SecurityCheckResult,
    guard,
    check_input,
    check_output,
)

__all__ = [
    # Basic prompt guard (pattern-based)
    "PromptGuard",
    "prompt_guard",
    # Sanitizer
    "Sanitizer",
    "sanitizer",
    # Audit
    "AuditLogger",
    "audit_logger",
    # NeMo Guardrails (LLM-based)
    "CookHeroGuard",
    "GuardResult",
    "SecurityCheckResult",
    "guard",
    "check_input",
    "check_output",
]
