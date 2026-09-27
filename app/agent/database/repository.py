"""
Agent 模块数据访问仓库

提供 Agent Session 和 Message 的 CRUD 操作。
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import select, delete, func
from sqlalchemy.orm import selectinload

from app.agent.database.models import (
    AgentMessageModel,
    AgentRunModel,
    AgentSessionModel,
)
from app.database.session import get_session_context

logger = logging.getLogger(__name__)


class AgentRepository:
    """
    Agent 数据访问仓库。
    管理 Agent Session 和 Message 的持久化。
    """

    # ==================== Session Operations ====================

    async def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        user_id: str = "",
        title: Optional[str] = None,
    ) -> AgentSessionModel:
        """获取或创建 Agent Session。"""
        async with get_session_context() as session:
            if session_id:
                try:
                    sess_uuid = uuid.UUID(session_id)
                    stmt = (
                        select(AgentSessionModel)
                        .options(selectinload(AgentSessionModel.messages))
                        .where(AgentSessionModel.id == sess_uuid)
                    )
                    result = await session.execute(stmt)
                    agent_session = result.scalar_one_or_none()
                    if agent_session:
                        return agent_session
                except ValueError:
                    logger.warning(f"Invalid session_id format: {session_id}")

            # Create new session
            agent_session = AgentSessionModel(
                user_id=user_id,
                title=title,
            )
            session.add(agent_session)
            await session.flush()
            return agent_session

    async def get_session(self, session_id: str) -> Optional[AgentSessionModel]:
        """根据 ID 获取 Session。"""
        async with get_session_context() as session:
            try:
                sess_uuid = uuid.UUID(session_id)
            except ValueError:
                return None

            stmt = (
                select(AgentSessionModel)
                .options(selectinload(AgentSessionModel.messages))
                .where(AgentSessionModel.id == sess_uuid)
            )
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def list_sessions(
        self,
        user_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[dict], int]:
        """列出 Sessions。"""
        async with get_session_context() as session:
            # Build filters
            filters = []
            if user_id:
                filters.append(AgentSessionModel.user_id == user_id)

            # Get total count
            count_stmt = select(func.count(AgentSessionModel.id))
            if filters:
                count_stmt = count_stmt.where(*filters)
            count_result = await session.execute(count_stmt)
            total_count = count_result.scalar() or 0

            # Get paginated sessions
            stmt = (
                select(AgentSessionModel)
                .options(selectinload(AgentSessionModel.messages))
                .order_by(AgentSessionModel.updated_at.desc())
                .limit(limit)
                .offset(offset)
            )
            if filters:
                stmt = stmt.where(*filters)

            result = await session.execute(stmt)
            sessions = result.scalars().all()

            return [s.to_dict() for s in sessions], total_count

    async def delete_session(self, session_id: str) -> bool:
        """删除 Session 及其所有消息。"""
        async with get_session_context() as session:
            try:
                sess_uuid = uuid.UUID(session_id)
            except ValueError:
                return False

            stmt = select(AgentSessionModel).where(AgentSessionModel.id == sess_uuid)
            result = await session.execute(stmt)
            agent_session = result.scalar_one_or_none()
            if not agent_session:
                return False

            await session.delete(agent_session)
            return True

    async def update_session_title(
        self,
        session_id: str,
        title: str,
    ) -> bool:
        """更新 Session 标题。"""
        async with get_session_context() as session:
            try:
                sess_uuid = uuid.UUID(session_id)
            except ValueError:
                return False

            stmt = select(AgentSessionModel).where(AgentSessionModel.id == sess_uuid)
            result = await session.execute(stmt)
            agent_session = result.scalar_one_or_none()

            if not agent_session:
                return False

            agent_session.title = title
            agent_session.updated_at = datetime.utcnow()
            await session.flush()
            return True

    # ==================== Message Operations ====================

    async def save_message(
        self,
        session_id: str,
        role: str,
        content: str,
        trace: Optional[list] = None,
        tool_calls: Optional[list] = None,
        tool_call_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        thinking_duration_ms: Optional[int] = None,
        answer_duration_ms: Optional[int] = None,
        run_id: Optional[str] = None,
    ) -> AgentMessageModel:
        """保存消息到 Session。"""
        async with get_session_context() as session:
            sess_uuid = uuid.UUID(session_id)

            # Update session timestamp
            stmt = select(AgentSessionModel).where(AgentSessionModel.id == sess_uuid)
            result = await session.execute(stmt)
            agent_session = result.scalar_one_or_none()

            if not agent_session:
                raise ValueError(f"Session {session_id} not found")

            agent_session.updated_at = datetime.utcnow()

            # Create message
            message = AgentMessageModel(
                session_id=sess_uuid,
                role=role,
                content=content,
                trace=trace,
                tool_calls=tool_calls,
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                thinking_duration_ms=thinking_duration_ms,
                answer_duration_ms=answer_duration_ms,
                run_id=run_id,
            )
            session.add(message)
            await session.flush()
            return message

    async def get_messages(
        self,
        session_id: str,
        limit: Optional[int] = None,
    ) -> List[AgentMessageModel]:
        """获取 Session 的消息列表。"""
        async with get_session_context() as session:
            sess_uuid = uuid.UUID(session_id)
            stmt = (
                select(AgentMessageModel)
                .where(AgentMessageModel.session_id == sess_uuid)
                .order_by(AgentMessageModel.created_at)
            )
            if limit:
                stmt = stmt.limit(limit)

            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_recent_messages(
        self,
        session_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> List[dict]:
        """
        获取最近的消息，用于上下文组装。

        Args:
            session_id: Session ID
            skip: 跳过的消息数（已压缩的消息）
            limit: 返回的消息数
        """
        async with get_session_context() as session:
            sess_uuid = uuid.UUID(session_id)

            # Get messages ordered by created_at, skip compressed ones
            stmt = (
                select(AgentMessageModel)
                .where(AgentMessageModel.session_id == sess_uuid)
                .order_by(AgentMessageModel.created_at)
                .offset(skip)
                .limit(limit)
            )

            result = await session.execute(stmt)
            messages = result.scalars().all()

            result_list = []
            for msg in messages:
                msg_dict: dict[str, Any] = {
                    "role": msg.role,
                    "content": msg.content,
                }
                if msg.tool_calls:
                    msg_dict["tool_calls"] = msg.tool_calls
                    if not msg.content:
                        msg_dict["content"] = None
                if msg.role == "tool":
                    if msg.tool_call_id:
                        msg_dict["tool_call_id"] = msg.tool_call_id
                    if msg.tool_name:
                        msg_dict["name"] = msg.tool_name
                result_list.append(msg_dict)

            return result_list

    async def get_message_count(self, session_id: str) -> int:
        """获取 Session 的消息总数。"""
        async with get_session_context() as session:
            try:
                sess_uuid = uuid.UUID(session_id)
            except ValueError:
                return 0

            stmt = select(func.count(AgentMessageModel.id)).where(
                AgentMessageModel.session_id == sess_uuid
            )
            result = await session.execute(stmt)
            return result.scalar() or 0

    # ==================== Compression Operations ====================

    async def get_compressed_summary(
        self, session_id: str
    ) -> tuple[Optional[str], int]:
        """获取压缩摘要和已压缩消息数。"""
        async with get_session_context() as session:
            try:
                sess_uuid = uuid.UUID(session_id)
            except ValueError:
                return None, 0

            stmt = select(
                AgentSessionModel.compressed_summary,
                AgentSessionModel.compressed_count,
            ).where(AgentSessionModel.id == sess_uuid)

            result = await session.execute(stmt)
            row = result.one_or_none()

            if row:
                return row[0], row[1]
            return None, 0

    async def update_compressed_summary(
        self,
        session_id: str,
        summary: str,
        message_count: int,
    ) -> bool:
        """更新压缩摘要。"""
        async with get_session_context() as session:
            try:
                sess_uuid = uuid.UUID(session_id)
            except ValueError:
                return False

            stmt = select(AgentSessionModel).where(AgentSessionModel.id == sess_uuid)
            result = await session.execute(stmt)
            agent_session = result.scalar_one_or_none()

            if not agent_session:
                return False

            agent_session.compressed_summary = summary
            agent_session.compressed_count = message_count
            await session.flush()

            logger.info(
                "Updated compressed summary for session %s (messages: %d)",
                session_id,
                message_count,
            )
            return True

    # ==================== Agent Run Operations ====================

    async def upsert_run(self, snapshot: dict) -> dict:
        """
        插入或更新一次 Agent 执行的聚合记录。

        snapshot 由 tracing.TraceRunState.snapshot() 生成，包含 trace/run 标识、
        状态、耗时、token 计数、工具/Subagent 计数以及 trace 明细。
        使用 upsert 可以同时满足"开始时落库"和"结束时更新"两种调用。
        """
        run_id = snapshot.get("run_id")
        if not run_id:
            raise ValueError("snapshot.run_id is required")

        session_id = snapshot.get("session_id")
        try:
            session_uuid = uuid.UUID(str(session_id)) if session_id else None
        except (ValueError, TypeError):
            session_uuid = None

        async with get_session_context() as session:
            stmt = select(AgentRunModel).where(AgentRunModel.run_id == run_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

            fields = {
                "trace_id": snapshot.get("trace_id"),
                "user_id": snapshot.get("user_id"),
                "session_id": session_uuid,
                "agent_name": snapshot.get("agent_name") or "default",
                "status": snapshot.get("status") or "running",
                "started_at": _parse_dt(snapshot.get("started_at"))
                or datetime.utcnow(),
                "finished_at": _parse_dt(snapshot.get("finished_at")),
                "duration_ms": snapshot.get("duration_ms"),
                "ttft_ms": snapshot.get("ttft_ms"),
                "iteration_count": snapshot.get("iteration_count", 0),
                "llm_call_count": snapshot.get("llm_call_count", 0),
                "tool_call_count": snapshot.get("tool_call_count", 0),
                "subagent_call_count": snapshot.get("subagent_call_count", 0),
                "tool_failure_count": snapshot.get("tool_failure_count", 0),
                "input_tokens": snapshot.get("input_tokens", 0),
                "output_tokens": snapshot.get("output_tokens", 0),
                "total_tokens": snapshot.get("total_tokens", 0),
                "error_type": snapshot.get("error_type"),
                "error_message": snapshot.get("error_message"),
                "source": snapshot.get("source") or "online",
                "experiment_id": snapshot.get("experiment_id"),
                "dataset_case_id": snapshot.get("dataset_case_id"),
                "repeat_index": snapshot.get("repeat_index"),
                "config_hash": snapshot.get("config_hash"),
                "trace": snapshot.get("trace") or [],
            }

            if row is None:
                row = AgentRunModel(trace_id=fields["trace_id"], run_id=run_id)
                session.add(row)

            for key, value in fields.items():
                setattr(row, key, value)
            row.updated_at = datetime.utcnow()

            await session.flush()
            return row.to_dict()

    async def get_run(self, run_id: str) -> Optional[dict]:
        """根据 run_id 获取一次 Agent 执行记录。"""
        async with get_session_context() as session:
            stmt = select(AgentRunModel).where(AgentRunModel.run_id == run_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return row.to_dict() if row else None

    async def list_runs(
        self,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        experiment_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[List[dict], int]:
        """按用户/会话/实验列出 Agent 执行记录，便于评测与排查。"""
        async with get_session_context() as session:
            filters = []
            if user_id:
                filters.append(AgentRunModel.user_id == user_id)
            if session_id:
                try:
                    filters.append(AgentRunModel.session_id == uuid.UUID(session_id))
                except ValueError:
                    return [], 0
            if experiment_id:
                filters.append(AgentRunModel.experiment_id == experiment_id)
            if status:
                filters.append(AgentRunModel.status == status)

            count_stmt = select(func.count(AgentRunModel.id))
            if filters:
                count_stmt = count_stmt.where(*filters)
            count_result = await session.execute(count_stmt)
            total = count_result.scalar() or 0

            stmt = (
                select(AgentRunModel)
                .order_by(AgentRunModel.started_at.desc())
                .limit(limit)
                .offset(offset)
            )
            if filters:
                stmt = stmt.where(*filters)

            result = await session.execute(stmt)
            runs = result.scalars().all()
            summaries = [r.to_dict() for r in runs]
            for summary in summaries:
                summary.pop("trace", None)
            return summaries, total


def _parse_dt(value: Any) -> Optional[datetime]:
    """把 ISO 字符串/None 解析为 naive UTC datetime。"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        parsed = datetime.fromisoformat(str(value))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


# Singleton instance
agent_repository = AgentRepository()
