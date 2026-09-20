# app/database/llm_usage_repository.py
"""
Repository for LLM usage statistics data access.
Handles CRUD operations and aggregation queries for LLMUsageLogModel.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, and_

from app.database.models import LLMUsageLogModel
from app.database.session import get_session_context

logger = logging.getLogger(__name__)


class LLMUsageRepository:
    """
    Data access layer for LLM usage statistics.
    Provides methods for creating logs and querying aggregated statistics.
    """

    # ==================== Create Log ====================

    async def create_log(
        self,
        request_id: str,
        module_name: str,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        model_name: Optional[str] = None,
        tool_name: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        total_tokens: Optional[int] = None,
        duration_ms: Optional[int] = None,
    ) -> LLMUsageLogModel:
        """
        Create a new LLM usage log entry.

        Args:
            request_id: Unique request identifier
            module_name: Name of the module that made the LLM call
            user_id: User ID (if available)
            conversation_id: Conversation ID (if available)
            model_name: Name of the LLM model used
            tool_name: Name of the tool used (if applicable)
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            total_tokens: Total tokens used
            duration_ms: Call duration in milliseconds

        Returns:
            Created LLMUsageLogModel instance
        """
        async with get_session_context() as session:
            log = LLMUsageLogModel(
                id=uuid.uuid4(),
                request_id=request_id,
                module_name=module_name,
                user_id=user_id,
                conversation_id=uuid.UUID(conversation_id) if conversation_id else None,
                model_name=model_name,
                tool_name=tool_name,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                duration_ms=duration_ms,
            )
            session.add(log)
            await session.commit()

            logger.debug(
                "Created LLM usage log: module=%s, model=%s, tool=%s, tokens=%s",
                module_name,
                model_name,
                tool_name,
                total_tokens,
            )
            return log

    # ==================== Summary Statistics ====================

    async def get_summary(
        self,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get aggregated summary statistics for LLM usage.

        Args:
            user_id: Filter by user ID
            conversation_id: Filter by conversation ID
            start_date: Filter by start date
            end_date: Filter by end date

        Returns:
            Dictionary with summary statistics
        """
        async with get_session_context() as session:
            conditions = self._build_conditions(
                user_id=user_id,
                conversation_id=conversation_id,
                start_date=start_date,
                end_date=end_date,
            )

            stmt = select(
                func.count(LLMUsageLogModel.id).label("total_calls"),
                func.sum(LLMUsageLogModel.input_tokens).label("total_input_tokens"),
                func.sum(LLMUsageLogModel.output_tokens).label("total_output_tokens"),
                func.sum(LLMUsageLogModel.total_tokens).label("total_tokens"),
                func.avg(LLMUsageLogModel.total_tokens).label("avg_tokens_per_call"),
                func.avg(LLMUsageLogModel.duration_ms).label("avg_duration_ms"),
                func.min(LLMUsageLogModel.created_at).label("first_call"),
                func.max(LLMUsageLogModel.created_at).label("last_call"),
            )

            if conditions:
                stmt = stmt.where(and_(*conditions))

            result = await session.execute(stmt)
            row = result.one()

            return {
                "total_calls": row.total_calls or 0,
                "total_input_tokens": row.total_input_tokens or 0,
                "total_output_tokens": row.total_output_tokens or 0,
                "total_tokens": row.total_tokens or 0,
                "avg_tokens_per_call": float(row.avg_tokens_per_call) if row.avg_tokens_per_call else 0,
                "avg_duration_ms": float(row.avg_duration_ms) if row.avg_duration_ms else 0,
                "period": {
                    "start": start_date.isoformat() if start_date else (
                        row.first_call.isoformat() if row.first_call else None
                    ),
                    "end": end_date.isoformat() if end_date else (
                        row.last_call.isoformat() if row.last_call else None
                    ),
                },
            }

    # ==================== Time Series Data ====================

    async def get_time_series(
        self,
        days: int = 7,
        granularity: str = "hour",
        user_id: Optional[str] = None,
        module_name: Optional[str] = None,
        model_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get time series data for LLM usage.

        Args:
            days: Number of days to look back
            granularity: Time grouping ("hour" or "day")
            user_id: Filter by user ID
            module_name: Filter by module name
            model_name: Filter by model name

        Returns:
            List of time series data points
        """
        async with get_session_context() as session:
            start_date = datetime.utcnow() - timedelta(days=days)

            conditions = [LLMUsageLogModel.created_at >= start_date]
            if user_id:
                conditions.append(LLMUsageLogModel.user_id == user_id)
            if module_name:
                conditions.append(LLMUsageLogModel.module_name == module_name)
            if model_name:
                conditions.append(LLMUsageLogModel.model_name == model_name)

            # Time grouping
            if granularity == "day":
                date_trunc = func.date_trunc("day", LLMUsageLogModel.created_at)
            else:
                date_trunc = func.date_trunc("hour", LLMUsageLogModel.created_at)

            stmt = (
                select(
                    date_trunc.label("period"),
                    func.count(LLMUsageLogModel.id).label("call_count"),
                    func.sum(LLMUsageLogModel.input_tokens).label("input_tokens"),
                    func.sum(LLMUsageLogModel.output_tokens).label("output_tokens"),
                    func.sum(LLMUsageLogModel.total_tokens).label("total_tokens"),
                    func.avg(LLMUsageLogModel.duration_ms).label("avg_duration_ms"),
                )
                .where(and_(*conditions))
                .group_by(date_trunc)
                .order_by(date_trunc)
            )

            result = await session.execute(stmt)
            rows = result.all()

            return [
                {
                    "period": row.period.isoformat() if row.period else None,
                    "call_count": row.call_count,
                    "input_tokens": row.input_tokens or 0,
                    "output_tokens": row.output_tokens or 0,
                    "total_tokens": row.total_tokens or 0,
                    "avg_duration_ms": float(row.avg_duration_ms) if row.avg_duration_ms else 0,
                }
                for row in rows
            ]

    # ==================== Distribution Statistics ====================

    async def get_distribution_by_module(
        self,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get usage distribution grouped by module.

        Returns:
            List of module statistics
        """
        async with get_session_context() as session:
            conditions = self._build_conditions(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
            )

            stmt = select(
                LLMUsageLogModel.module_name,
                func.count(LLMUsageLogModel.id).label("call_count"),
                func.sum(LLMUsageLogModel.total_tokens).label("total_tokens"),
                func.avg(LLMUsageLogModel.total_tokens).label("avg_tokens"),
                func.avg(LLMUsageLogModel.duration_ms).label("avg_duration_ms"),
            )

            if conditions:
                stmt = stmt.where(and_(*conditions))

            stmt = stmt.group_by(LLMUsageLogModel.module_name).order_by(
                func.sum(LLMUsageLogModel.total_tokens).desc()
            )

            result = await session.execute(stmt)
            rows = result.all()

            return [
                {
                    "module_name": row.module_name,
                    "call_count": row.call_count,
                    "total_tokens": row.total_tokens or 0,
                    "avg_tokens": float(row.avg_tokens) if row.avg_tokens else 0,
                    "avg_duration_ms": float(row.avg_duration_ms) if row.avg_duration_ms else 0,
                }
                for row in rows
            ]

    async def get_distribution_by_model(
        self,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get usage distribution grouped by model.

        Returns:
            List of model statistics
        """
        async with get_session_context() as session:
            conditions = self._build_conditions(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
            )

            stmt = select(
                LLMUsageLogModel.model_name,
                func.count(LLMUsageLogModel.id).label("call_count"),
                func.sum(LLMUsageLogModel.total_tokens).label("total_tokens"),
                func.avg(LLMUsageLogModel.total_tokens).label("avg_tokens"),
                func.avg(LLMUsageLogModel.duration_ms).label("avg_duration_ms"),
            )

            if conditions:
                stmt = stmt.where(and_(*conditions))

            stmt = stmt.group_by(LLMUsageLogModel.model_name).order_by(
                func.sum(LLMUsageLogModel.total_tokens).desc()
            )

            result = await session.execute(stmt)
            rows = result.all()

            return [
                {
                    "model_name": row.model_name or "unknown",
                    "call_count": row.call_count,
                    "total_tokens": row.total_tokens or 0,
                    "avg_tokens": float(row.avg_tokens) if row.avg_tokens else 0,
                    "avg_duration_ms": float(row.avg_duration_ms) if row.avg_duration_ms else 0,
                }
                for row in rows
            ]

    # ==================== Conversation Level Stats ====================

    async def get_by_conversation(
        self,
        conversation_id: str,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Get LLM usage logs for a specific conversation.

        Returns:
            List of usage log entries
        """
        async with get_session_context() as session:
            stmt = (
                select(LLMUsageLogModel)
                .where(LLMUsageLogModel.conversation_id == uuid.UUID(conversation_id))
                .order_by(LLMUsageLogModel.created_at.desc())
                .limit(limit)
            )

            result = await session.execute(stmt)
            logs = result.scalars().all()

            return [self._log_to_dict(log) for log in logs]

    # ==================== Distinct Values ====================

    async def get_distinct_modules(self) -> List[str]:
        """
        Get list of distinct module names that have logged LLM usage.

        Returns:
            List of unique module names
        """
        async with get_session_context() as session:
            stmt = (
                select(LLMUsageLogModel.module_name)
                .distinct()
                .where(LLMUsageLogModel.module_name.isnot(None))
                .order_by(LLMUsageLogModel.module_name)
            )

            result = await session.execute(stmt)
            rows = result.scalars().all()

            return list(rows)

    async def get_distinct_models(self) -> List[str]:
        """
        Get list of distinct model names that have been used.

        Returns:
            List of unique model names
        """
        async with get_session_context() as session:
            stmt = (
                select(LLMUsageLogModel.model_name)
                .distinct()
                .where(LLMUsageLogModel.model_name.isnot(None))
                .order_by(LLMUsageLogModel.model_name)
            )

            result = await session.execute(stmt)
            rows = result.scalars().all()

            return list(rows) # type: ignore

    async def get_distinct_tools(self) -> List[str]:
        """
        Get list of distinct tool names that have been used.

        Returns:
            List of unique tool names
        """
        async with get_session_context() as session:
            stmt = (
                select(LLMUsageLogModel.tool_name)
                .distinct()
                .where(LLMUsageLogModel.tool_name.isnot(None))
                .order_by(LLMUsageLogModel.tool_name)
            )

            result = await session.execute(stmt)
            rows = result.scalars().all()

            return list(rows) # type: ignore

    async def get_distribution_by_tool(
        self,
        user_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        model_name: Optional[str] = None,
        module_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get usage distribution grouped by tool.

        Args:
            user_id: Filter by user ID
            start_date: Filter by start date
            end_date: Filter by end date
            model_name: Filter by model name
            module_name: Filter by module name

        Returns:
            List of tool statistics
        """
        async with get_session_context() as session:
            conditions = self._build_conditions(
                user_id=user_id,
                start_date=start_date,
                end_date=end_date,
            )

            if model_name:
                conditions.append(LLMUsageLogModel.model_name == model_name)
            if module_name:
                conditions.append(LLMUsageLogModel.module_name == module_name)

            stmt = select(
                LLMUsageLogModel.tool_name,
                func.count(LLMUsageLogModel.id).label("call_count"),
                func.sum(LLMUsageLogModel.input_tokens).label("input_tokens"),
                func.sum(LLMUsageLogModel.output_tokens).label("output_tokens"),
                func.sum(LLMUsageLogModel.total_tokens).label("total_tokens"),
                func.avg(LLMUsageLogModel.total_tokens).label("avg_tokens"),
                func.avg(LLMUsageLogModel.duration_ms).label("avg_duration_ms"),
            )

            if conditions:
                stmt = stmt.where(and_(*conditions))

            stmt = stmt.group_by(LLMUsageLogModel.tool_name).order_by(
                func.sum(LLMUsageLogModel.total_tokens).desc()
            )

            result = await session.execute(stmt)
            rows = result.all()

            return [
                {
                    "tool_name": row.tool_name or "no_tool",
                    "call_count": row.call_count,
                    "input_tokens": row.input_tokens or 0,
                    "output_tokens": row.output_tokens or 0,
                    "total_tokens": row.total_tokens or 0,
                    "avg_tokens": float(row.avg_tokens) if row.avg_tokens else 0,
                    "avg_duration_ms": float(row.avg_duration_ms) if row.avg_duration_ms else 0,
                }
                for row in rows
            ]

    async def get_tool_time_series(
        self,
        days: int = 7,
        granularity: str = "hour",
        user_id: Optional[str] = None,
        model_name: Optional[str] = None,
        module_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get time series data for tool usage.

        Args:
            days: Number of days to look back
            granularity: Time grouping ("hour" or "day")
            user_id: Filter by user ID
            model_name: Filter by model name
            module_name: Filter by module name

        Returns:
            List of time series data points
        """
        async with get_session_context() as session:
            start_date = datetime.utcnow() - timedelta(days=days)

            conditions = [LLMUsageLogModel.created_at >= start_date]
            if user_id:
                conditions.append(LLMUsageLogModel.user_id == user_id)
            if model_name:
                conditions.append(LLMUsageLogModel.model_name == model_name)
            if module_name:
                conditions.append(LLMUsageLogModel.module_name == module_name)

            # Time grouping
            if granularity == "day":
                date_trunc = func.date_trunc("day", LLMUsageLogModel.created_at)
            else:
                date_trunc = func.date_trunc("hour", LLMUsageLogModel.created_at)

            stmt = (
                select(
                    date_trunc.label("period"),
                    LLMUsageLogModel.tool_name,
                    func.count(LLMUsageLogModel.id).label("call_count"),
                    func.sum(LLMUsageLogModel.input_tokens).label("input_tokens"),
                    func.sum(LLMUsageLogModel.output_tokens).label("output_tokens"),
                    func.sum(LLMUsageLogModel.total_tokens).label("total_tokens"),
                    func.avg(LLMUsageLogModel.duration_ms).label("avg_duration_ms"),
                )
                .where(and_(*conditions))
                .group_by(date_trunc, LLMUsageLogModel.tool_name)
                .order_by(date_trunc, LLMUsageLogModel.tool_name)
            )

            result = await session.execute(stmt)
            rows = result.all()

            return [
                {
                    "period": row.period.isoformat() if row.period else None,
                    "tool_name": row.tool_name or "no_tool",
                    "call_count": row.call_count,
                    "input_tokens": row.input_tokens or 0,
                    "output_tokens": row.output_tokens or 0,
                    "total_tokens": row.total_tokens or 0,
                    "avg_duration_ms": float(row.avg_duration_ms) if row.avg_duration_ms else 0,
                }
                for row in rows
            ]

    # ==================== Helper Methods ====================

    def _log_to_dict(self, log: LLMUsageLogModel) -> Dict[str, Any]:
        """Convert LLMUsageLogModel to dictionary."""
        return {
            "id": str(log.id),
            "request_id": log.request_id,
            "module_name": log.module_name,
            "user_id": log.user_id,
            "conversation_id": str(log.conversation_id) if log.conversation_id else None,
            "model_name": log.model_name,
            "tool_name": log.tool_name,
            "input_tokens": log.input_tokens,
            "output_tokens": log.output_tokens,
            "total_tokens": log.total_tokens,
            "duration_ms": log.duration_ms,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }

    def _build_conditions(
        self,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List:
        """Build filter conditions for queries."""
        conditions = []

        if user_id:
            conditions.append(LLMUsageLogModel.user_id == user_id)
        if conversation_id:
            conditions.append(
                LLMUsageLogModel.conversation_id == uuid.UUID(conversation_id)
            )
        if start_date:
            conditions.append(LLMUsageLogModel.created_at >= start_date)
        if end_date:
            conditions.append(LLMUsageLogModel.created_at <= end_date)

        return conditions


# Singleton instance
llm_usage_repository = LLMUsageRepository()
