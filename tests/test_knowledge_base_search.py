from types import SimpleNamespace

import pytest

from app.agent.tools.common.knowledge_base_search import KnowledgeBaseSearchTool
from app.services.rag_service import rag_service_instance


@pytest.mark.asyncio
async def test_execute_forwards_user_id_to_rag(monkeypatch):
    captured = {}

    async def fake_retrieve(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            rewritten_query=kwargs["query"],
            context="番茄炒蛋做法",
            sources=[{"source": "test"}],
            documents=[object()],
        )

    monkeypatch.setattr(rag_service_instance, "retrieve", fake_retrieve)

    result = await KnowledgeBaseSearchTool().execute(
        query="番茄炒蛋怎么做",
        user_id="user-123",
    )

    assert result.success is True
    assert captured == {
        "query": "番茄炒蛋怎么做",
        "skip_rewrite": False,
        "user_id": "user-123",
    }
    assert result.data["document_count"] == 1
    assert result.data["sources"] == [{"source": "test"}]
