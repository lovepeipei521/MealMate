"""
Security audit logging for CookHero.

Provides structured logging for security-relevant events
to support compliance and incident investigation.
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from fastapi import Request


class AuditEventType(Enum):
    """Types of security audit events."""

    # Authentication events
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILURE = "auth.login.failure"
    LOGOUT = "auth.logout"
    TOKEN_CREATED = "auth.token.created"
    TOKEN_REFRESH = "auth.token.refresh"
    TOKEN_INVALID = "auth.token.invalid"

    # Account security
    ACCOUNT_LOCKED = "account.locked"
    ACCOUNT_UNLOCKED = "account.unlocked"
    PASSWORD_CHANGED = "account.password.changed"
    PROFILE_UPDATED = "account.profile.updated"

    # Rate limiting
    RATE_LIMIT_EXCEEDED = "security.rate_limit.exceeded"

    # Input validation
    PROMPT_INJECTION_BLOCKED = "security.prompt_injection.blocked"
    PROMPT_INJECTION_WARNING = "security.prompt_injection.warning"
    INPUT_VALIDATION_FAILED = "security.input.validation_failed"

    # Data access
    CONVERSATION_CREATED = "data.conversation.created"
    CONVERSATION_DELETED = "data.conversation.deleted"
    DOCUMENT_CREATED = "data.document.created"
    DOCUMENT_DELETED = "data.document.deleted"

    # System events
    CONFIG_CHANGED = "system.config.changed"
    ERROR = "system.error"


class AuditLogger:
    """
    Structured audit logger for security events.

    Logs security events in JSON format for easy parsing
    and analysis by SIEM systems.
    """

    def __init__(self, logger_name: str = "security.audit"):
        """
        Initialize audit logger.

        Args:
            logger_name: Name for the audit logger
        """
        self.logger = logging.getLogger(logger_name)

        # Ensure audit logs are always captured
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def _get_client_info(self, request: Optional[Request]) -> Dict[str, Any]:
        """Extract client information from request."""
        if not request:
            return {}

        # Get client IP (handle proxy headers)
        client_ip = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        if not client_ip:
            client_ip = request.headers.get("X-Real-IP", "")
        if not client_ip:
            client_ip = request.client.host if request.client else "unknown"

        return {
            "ip": client_ip,
            "user_agent": request.headers.get("User-Agent", ""),
            "path": str(request.url.path),
            "method": request.method,
        }

    def log(
        self,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        username: Optional[str] = None,
        request: Optional[Request] = None,
        success: bool = True,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """
        Log a security audit event.

        Args:
            event_type: Type of security event
            user_id: User ID if applicable
            username: Username if applicable
            request: FastAPI request object for client info
            success: Whether the operation succeeded
            details: Additional event details
            error: Error message if applicable
        """
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type.value,
            "success": success,
            "user_id": user_id,
            "username": username,
            "client": self._get_client_info(request),
            "details": details or {},
        }

        if error:
            event["error"] = error

        # Determine log level based on event type and success
        if not success or event_type in (
            AuditEventType.PROMPT_INJECTION_BLOCKED,
            AuditEventType.RATE_LIMIT_EXCEEDED,
            AuditEventType.ACCOUNT_LOCKED,
        ):
            log_level = logging.WARNING
        elif event_type == AuditEventType.ERROR:
            log_level = logging.ERROR
        else:
            log_level = logging.INFO

        # Log as JSON for easy parsing
        self.logger.log(log_level, json.dumps(event, ensure_ascii=False))

    # Convenience methods for common events

    def login_success(
        self,
        username: str,
        user_id: str,
        request: Optional[Request] = None,
    ) -> None:
        """Log successful login."""
        self.log(
            AuditEventType.LOGIN_SUCCESS,
            user_id=user_id,
            username=username,
            request=request,
            success=True,
        )

    def login_failure(
        self,
        username: str,
        request: Optional[Request] = None,
        reason: str = "invalid_credentials",
    ) -> None:
        """Log failed login attempt."""
        self.log(
            AuditEventType.LOGIN_FAILURE,
            username=username,
            request=request,
            success=False,
            details={"reason": reason},
        )

    def account_locked(
        self,
        username: str,
        request: Optional[Request] = None,
        failed_attempts: int = 0,
        lockout_minutes: int = 15,
    ) -> None:
        """Log account lockout due to failed attempts."""
        self.log(
            AuditEventType.ACCOUNT_LOCKED,
            username=username,
            request=request,
            success=False,
            details={
                "failed_attempts": failed_attempts,
                "lockout_minutes": lockout_minutes,
            },
        )

    def rate_limit_exceeded(
        self,
        request: Optional[Request] = None,
        user_id: Optional[str] = None,
        endpoint: str = "",
        limit: int = 0,
        current: int = 0,
    ) -> None:
        """Log rate limit exceeded event."""
        self.log(
            AuditEventType.RATE_LIMIT_EXCEEDED,
            user_id=user_id,
            request=request,
            success=False,
            details={
                "endpoint": endpoint,
                "limit": limit,
                "current": current,
            },
        )

    def prompt_injection_blocked(
        self,
        user_id: Optional[str] = None,
        request: Optional[Request] = None,
        patterns: Optional[list] = None,
        input_preview: str = "",
    ) -> None:
        """Log blocked prompt injection attempt."""
        self.log(
            AuditEventType.PROMPT_INJECTION_BLOCKED,
            user_id=user_id,
            request=request,
            success=False,
            details={
                "patterns": patterns or [],
                "input_preview": input_preview[:100] if input_preview else "",
            },
        )

    def token_invalid(
        self,
        request: Optional[Request] = None,
        reason: str = "invalid",
    ) -> None:
        """Log invalid token attempt."""
        self.log(
            AuditEventType.TOKEN_INVALID,
            request=request,
            success=False,
            details={"reason": reason},
        )


# Global audit logger instance
audit_logger = AuditLogger()
