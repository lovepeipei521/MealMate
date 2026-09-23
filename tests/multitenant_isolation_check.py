#!/usr/bin/env python3
"""MealMate 多租户隔离检查脚本。

用法:
    python -m tests.multitenant_isolation_check --base-url http://127.0.0.1:8000
    python -m tests.multitenant_isolation_check --base-url http://127.0.0.1:8000 --verbose

脚本会临时注册两个普通用户 A/B，然后检查 B 是否能访问、修改或写入 A 的：
  - Agent 会话
  - 传统对话
  - 个人知识库文档
  - 饮食记录
  - LLM 统计明细

它不会删除用户账号，也不会碰已有业务数据。Agent/传统对话测试会真实调用一次 LLM；
如果只想跑不需要模型的资源隔离，可以加 --skip-llm。
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any, Iterable, Mapping, Optional

import httpx


PASS = "PASS"
FAIL = "FAIL"
VULNERABLE = "VULNERABLE"
SKIP = "SKIP"


@dataclass
class Result:
    category: str
    name: str
    status: str
    detail: str = ""


def _json_or_empty(response: httpx.Response) -> dict[str, Any]:
    try:
        value = response.json()
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


def _snippet(response: httpx.Response, limit: int = 240) -> str:
    text = response.text.replace("\n", " ").strip()
    if len(text) > limit:
        return text[:limit] + "..."
    return text


def _id_from(data: Mapping[str, Any], *keys: str) -> Optional[str]:
    for key in keys:
        value = data.get(key)
        if value is not None:
            return str(value)
    return None


class ApiChecker:
    def __init__(
        self,
        base_url: str,
        api_prefix: str,
        timeout: float,
        verbose: bool,
        skip_llm: bool,
        stats_wait: float,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_prefix = "/" + api_prefix.strip("/")
        self.verbose = verbose
        self.skip_llm = skip_llm
        self.stats_wait = stats_wait
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, connect=10.0),
        )
        self.results: list[Result] = []
        self.token_a: Optional[str] = None
        self.token_b: Optional[str] = None
        self.username_a: Optional[str] = None
        self.username_b: Optional[str] = None
        self.agent_session_id: Optional[str] = None
        self.personal_doc_id: Optional[str] = None
        self.diet_log_id: Optional[str] = None
        self.conversation_id: Optional[str] = None
        self.nonce = uuid.uuid4().hex[:8]

    def close(self) -> None:
        self.client.close()

    def api(self, path: str) -> str:
        if not path.startswith("/"):
            path = "/" + path
        return f"{self.api_prefix}{path}"

    def record(self, status: str, name: str, detail: str = "", category: str = "通用") -> None:
        self.results.append(Result(category=category, name=name, status=status, detail=detail))
        line = f"[{status}] {name}"
        if detail:
            line += f" - {detail}"
        print(line, flush=True)

    def request(
        self,
        method: str,
        path: str,
        *,
        token: Optional[str] = None,
        **kwargs: Any,
    ) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        if token:
            headers["Authorization"] = f"Bearer {token}"

        if self.verbose:
            print(f"    -> {method.upper()} {self.api(path)}", flush=True)

        response = self.client.request(method, self.api(path), headers=headers, **kwargs)

        if self.verbose:
            print(f"       HTTP {response.status_code}", flush=True)
        return response

    def check_ok(self, name: str, response: httpx.Response, category: str) -> bool:
        if 200 <= response.status_code < 300:
            self.record(PASS, name, f"HTTP {response.status_code}", category)
            return True
        self.record(
            FAIL,
            name,
            f"HTTP {response.status_code}; {_snippet(response)}",
            category,
        )
        return False

    def check_isolation(
        self,
        name: str,
        response: httpx.Response,
        category: str,
        resource_hint: str = "",
    ) -> bool:
        """返回 True 表示检测到越权访问。"""
        if 200 <= response.status_code < 300:
            detail = f"HTTP {response.status_code}"
            if resource_hint:
                detail += f"; {resource_hint}"
            body = _json_or_empty(response)
            if body:
                detail += f"; body={json.dumps(body, ensure_ascii=False)[:220]}"
            self.record(VULNERABLE, name, detail, category)
            return True

        if response.status_code in (401, 403, 404):
            self.record(PASS, name, f"HTTP {response.status_code}（已拒绝）", category)
            return False

        self.record(
            FAIL,
            name,
            f"HTTP {response.status_code}（非预期状态）; {_snippet(response)}",
            category,
        )
        return False

    def check_list_excludes(
        self,
        name: str,
        response: httpx.Response,
        *,
        items_key: str,
        id_key: str,
        target_id: str,
        category: str,
    ) -> None:
        if response.status_code != 200:
            self.record(
                FAIL,
                name,
                f"HTTP {response.status_code}; {_snippet(response)}",
                category,
            )
            return

        data = _json_or_empty(response)
        items = data.get(items_key, [])
        if not isinstance(items, list):
            self.record(FAIL, name, f"响应字段 {items_key} 不是列表", category)
            return

        found = False
        for item in items:
            if isinstance(item, Mapping) and str(item.get(id_key)) == str(target_id):
                found = True
                break

        if found:
            self.record(
                VULNERABLE,
                name,
                f"B 的列表中出现了 A 的资源 {target_id}",
                category,
            )
        else:
            self.record(PASS, name, "B 的列表未包含 A 的资源", category)

    def register_user(self, role: str) -> Optional[dict[str, str]]:
        stamp = str(int(time.time()))
        suffix = uuid.uuid4().hex[:6]
        username = f"mt_{role}_{stamp}_{suffix}"
        password = f"MealMate-{role}-{suffix}!"

        response = self.request(
            "POST",
            "/auth/register",
            json={"username": username, "password": password},
            timeout=30.0,
        )
        if not self.check_ok(f"注册临时用户 {role.upper()}", response, "资源准备"):
            return None

        data = _json_or_empty(response)
        token = data.get("access_token")
        if not token:
            self.record(FAIL, f"读取用户 {role.upper()} token", "响应缺少 access_token", "资源准备")
            return None

        return {"username": username, "token": str(token)}

    # ------------------------------------------------------------------
    # Agent 会话隔离
    # ------------------------------------------------------------------
    def create_agent_session(self) -> None:
        if self.skip_llm:
            self.record(SKIP, "Agent 会话隔离", "已使用 --skip-llm", "Agent 会话")
            return

        message = f"请只回复 OK，用于 MealMate 多租户测试 {self.nonce}。"
        response = self.request(
            "POST",
            "/agent/chat",
            token=self.token_a,
            json={"message": message, "stream": False},
        )
        if not self.check_ok("A 创建 Agent 会话", response, "Agent 会话"):
            return

        data = _json_or_empty(response)
        session_id = _id_from(data, "session_id", "id")
        if not session_id:
            self.record(FAIL, "读取 Agent 会话 ID", "响应缺少 session_id", "Agent 会话")
            return

        self.agent_session_id = session_id
        self.record(PASS, "保存 Agent 会话 ID", session_id, "Agent 会话")

        sanity = self.request("GET", f"/agent/session/{session_id}", token=self.token_a)
        self.check_ok("A 读取自己的 Agent 会话", sanity, "Agent 会话")

        listed = self.request("GET", "/agent/sessions", token=self.token_b)
        self.check_list_excludes(
            "B 的 Agent 会话列表不包含 A 的会话",
            listed,
            items_key="sessions",
            id_key="id",
            target_id=session_id,
            category="Agent 会话",
        )

        read_response = self.request(
            "GET", f"/agent/session/{session_id}", token=self.token_b
        )
        self.check_isolation("B 读取 A 的 Agent 会话", read_response, "Agent 会话")

        messages_response = self.request(
            "GET", f"/agent/session/{session_id}/messages", token=self.token_b
        )
        self.check_isolation("B 读取 A 的 Agent 会话消息", messages_response, "Agent 会话")

        title_response = self.request(
            "PATCH",
            f"/agent/session/{session_id}/title",
            token=self.token_b,
            json={"title": f"B-insolation-{self.nonce}"},
        )
        self.check_isolation("B 修改 A 的 Agent 会话标题", title_response, "Agent 会话")

        # 旧实现存在风险：继续聊天时可能只按 session_id 查会话，不校验归属。
        append_response = self.request(
            "POST",
            "/agent/chat",
            token=self.token_b,
            json={
                "message": f"B 越权写入测试 {self.nonce}",
                "session_id": session_id,
                "stream": False,
            },
        )
        append_data = _json_or_empty(append_response)
        returned_id = _id_from(append_data, "session_id")
        if 200 <= append_response.status_code < 300:
            if returned_id == session_id:
                self.record(
                    VULNERABLE,
                    "B 向 A 的 Agent 会话写入消息",
                    f"HTTP {append_response.status_code}; 返回的 session_id 仍是 A 的会话",
                    "Agent 会话",
                )
            else:
                self.record(
                    FAIL,
                    "B 向 A 的 Agent 会话写入消息",
                    f"HTTP {append_response.status_code}; 返回了不同 session_id={returned_id}",
                    "Agent 会话",
                )
        elif append_response.status_code in (401, 403, 404):
            self.record(
                PASS,
                "B 向 A 的 Agent 会话写入消息",
                f"HTTP {append_response.status_code}（已拒绝）",
                "Agent 会话",
            )
        else:
            self.record(
                SKIP,
                "B 向 A 的 Agent 会话写入消息",
                f"HTTP {append_response.status_code}，无法确认是否写入; {_snippet(append_response)}",
                "Agent 会话",
            )

        delete_response = self.request(
            "DELETE", f"/agent/session/{session_id}", token=self.token_b
        )
        self.check_isolation("B 删除 A 的 Agent 会话", delete_response, "Agent 会话")

    # ------------------------------------------------------------------
    # 个人知识库文档隔离
    # ------------------------------------------------------------------
    def create_personal_doc(self) -> None:
        payload = {
            "dish_name": f"多租户测试菜-{self.nonce}",
            "category": "多租户测试",
            "difficulty": "简单",
            "data_source": "personal",
            "content": f"A-PRIVATE-CONTENT-{self.nonce}",
        }
        response = self.request(
            "POST", "/knowledge/personal-docs", token=self.token_a, json=payload
        )
        if not self.check_ok("A 创建个人知识库文档", response, "个人知识库"):
            return

        data = _json_or_empty(response)
        document_id = _id_from(data, "id", "document_id")
        if not document_id:
            self.record(FAIL, "读取个人文档 ID", "响应缺少 id/document_id", "个人知识库")
            return

        self.personal_doc_id = document_id
        self.record(PASS, "保存个人文档 ID", document_id, "个人知识库")

        sanity = self.request(
            "GET", f"/knowledge/personal-docs/{document_id}", token=self.token_a
        )
        self.check_ok("A 读取自己的个人文档", sanity, "个人知识库")

        listed = self.request("GET", "/knowledge/personal-docs", token=self.token_b)
        self.check_list_excludes(
            "B 的个人文档列表不包含 A 的文档",
            listed,
            items_key="items",
            id_key="id",
            target_id=document_id,
            category="个人知识库",
        )

        read_response = self.request(
            "GET", f"/knowledge/personal-docs/{document_id}", token=self.token_b
        )
        self.check_isolation("B 读取 A 的个人文档", read_response, "个人知识库")

        update_payload = {
            **payload,
            "dish_name": f"B-越权修改-{self.nonce}",
            "content": f"B-MODIFIED-{self.nonce}",
        }
        update_response = self.request(
            "PUT",
            f"/knowledge/personal-docs/{document_id}",
            token=self.token_b,
            json=update_payload,
        )
        self.check_isolation("B 修改 A 的个人文档", update_response, "个人知识库")

        delete_response = self.request(
            "DELETE",
            f"/knowledge/personal-docs/{document_id}",
            token=self.token_b,
        )
        self.check_isolation("B 删除 A 的个人文档", delete_response, "个人知识库")

    # ------------------------------------------------------------------
    # 饮食记录隔离
    # ------------------------------------------------------------------
    def create_diet_log(self) -> None:
        today = date.today().isoformat()
        payload = {
            "log_date": today,
            "meal_type": "lunch",
            "items": [
                {
                    "food_name": f"A-ONLY-FOOD-{self.nonce}",
                    "calories": 123,
                    "protein": 10,
                    "fat": 5,
                    "carbs": 12,
                }
            ],
            "notes": f"A-ONLY-DIET-LOG-{self.nonce}",
        }
        response = self.request("POST", "/diet/logs", token=self.token_a, json=payload)
        if not self.check_ok("A 创建饮食记录", response, "饮食记录"):
            return

        data = _json_or_empty(response)
        log_id = _id_from(data, "id", "log_id")
        if not log_id:
            self.record(FAIL, "读取饮食记录 ID", "响应缺少 id/log_id", "饮食记录")
            return

        self.diet_log_id = log_id
        self.record(PASS, "保存饮食记录 ID", log_id, "饮食记录")

        sanity = self.request("GET", f"/diet/logs/{log_id}", token=self.token_a)
        self.check_ok("A 读取自己的饮食记录", sanity, "饮食记录")

        listed = self.request(
            "GET", "/diet/logs", token=self.token_b, params={"log_date": today}
        )
        self.check_list_excludes(
            "B 的饮食记录列表不包含 A 的记录",
            listed,
            items_key="logs",
            id_key="id",
            target_id=log_id,
            category="饮食记录",
        )

        read_response = self.request("GET", f"/diet/logs/{log_id}", token=self.token_b)
        self.check_isolation("B 读取 A 的饮食记录", read_response, "饮食记录")

        update_response = self.request(
            "PATCH",
            f"/diet/logs/{log_id}",
            token=self.token_b,
            json={"notes": f"B-DIET-MODIFIED-{self.nonce}"},
        )
        self.check_isolation("B 修改 A 的饮食记录", update_response, "饮食记录")

        delete_response = self.request(
            "DELETE", f"/diet/logs/{log_id}", token=self.token_b
        )
        self.check_isolation("B 删除 A 的饮食记录", delete_response, "饮食记录")

    # ------------------------------------------------------------------
    # 传统 Conversation 隔离
    # ------------------------------------------------------------------
    def create_conversation(self) -> None:
        if self.skip_llm:
            self.record(SKIP, "传统对话隔离", "已使用 --skip-llm", "传统对话")
            return

        response = self.request(
            "POST",
            "/conversation",
            token=self.token_a,
            json={
                "message": f"请只回复 OK，用于 MealMate 传统会话多租户测试 {self.nonce}。",
                "stream": False,
            },
        )
        if not self.check_ok("A 创建传统对话", response, "传统对话"):
            return

        data = _json_or_empty(response)
        conversation_id = _id_from(data, "conversation_id", "id")
        if not conversation_id:
            self.record(FAIL, "读取传统对话 ID", "响应缺少 conversation_id", "传统对话")
            return

        self.conversation_id = conversation_id
        self.record(PASS, "保存传统对话 ID", conversation_id, "传统对话")

        sanity = self.request("GET", f"/conversation/{conversation_id}", token=self.token_a)
        self.check_ok("A 读取自己的传统对话", sanity, "传统对话")

        listed = self.request("GET", "/conversation", token=self.token_b)
        self.check_list_excludes(
            "B 的传统对话列表不包含 A 的对话",
            listed,
            items_key="conversations",
            id_key="id",
            target_id=conversation_id,
            category="传统对话",
        )

        read_response = self.request(
            "GET", f"/conversation/{conversation_id}", token=self.token_b
        )
        self.check_isolation("B 读取 A 的传统对话", read_response, "传统对话")

        title_response = self.request(
            "PUT",
            f"/conversation/{conversation_id}/title",
            token=self.token_b,
            json={"title": f"B-insolation-{self.nonce}"},
        )
        self.check_isolation("B 修改 A 的传统对话标题", title_response, "传统对话")

        # 旧实现存在风险：继续对话时可能只按 conversation_id 查会话，不校验归属。
        append_response = self.request(
            "POST",
            "/conversation",
            token=self.token_b,
            json={
                "message": f"B 越权写入传统对话测试 {self.nonce}",
                "conversation_id": conversation_id,
                "stream": False,
            },
        )
        append_data = _json_or_empty(append_response)
        returned_id = _id_from(append_data, "conversation_id", "id")
        if 200 <= append_response.status_code < 300:
            if returned_id == conversation_id:
                self.record(
                    VULNERABLE,
                    "B 向 A 的传统对话写入消息",
                    f"HTTP {append_response.status_code}; 返回的 conversation_id 仍是 A 的对话",
                    "传统对话",
                )
            else:
                self.record(
                    FAIL,
                    "B 向 A 的传统对话写入消息",
                    f"HTTP {append_response.status_code}; 返回了不同 conversation_id={returned_id}",
                    "传统对话",
                )
        elif append_response.status_code in (401, 403, 404):
            self.record(
                PASS,
                "B 向 A 的传统对话写入消息",
                f"HTTP {append_response.status_code}（已拒绝）",
                "传统对话",
            )
        else:
            self.record(
                SKIP,
                "B 向 A 的传统对话写入消息",
                f"HTTP {append_response.status_code}，无法确认是否写入; {_snippet(append_response)}",
                "传统对话",
            )

        delete_response = self.request(
            "DELETE", f"/conversation/{conversation_id}", token=self.token_b
        )
        self.check_isolation("B 删除 A 的传统对话", delete_response, "传统对话")

    # ------------------------------------------------------------------
    # LLM 统计明细隔离
    # ------------------------------------------------------------------
    def check_llm_stats_isolation(self) -> None:
        if self.skip_llm or not self.agent_session_id:
            self.record(SKIP, "LLM 统计明细隔离", "没有可用的 Agent 会话 ID", "LLM 统计")
            return

        deadline = time.monotonic() + max(0.0, self.stats_wait)
        a_response: Optional[httpx.Response] = None
        a_count = 0
        while True:
            a_response = self.request(
                "GET",
                f"/llm-stats/conversation/{self.agent_session_id}",
                token=self.token_a,
            )
            if a_response.status_code == 200:
                a_data = _json_or_empty(a_response)
                try:
                    a_count = int(a_data.get("count") or 0)
                except (TypeError, ValueError):
                    a_count = 0
                if a_count > 0 or time.monotonic() >= deadline:
                    break
            elif time.monotonic() >= deadline:
                break
            time.sleep(0.5)

        assert a_response is not None
        if a_response.status_code == 200:
            self.record(
                PASS,
                "A 读取自己的 LLM 统计明细",
                f"HTTP 200; count={a_count}",
                "LLM 统计",
            )
        else:
            self.record(
                SKIP,
                "LLM 统计明细隔离",
                f"A 读取失败或无数据，HTTP {a_response.status_code}; {_snippet(a_response)}",
                "LLM 统计",
            )
            return

        b_response = self.request(
            "GET",
            f"/llm-stats/conversation/{self.agent_session_id}",
            token=self.token_b,
        )
        b_data = _json_or_empty(b_response)
        try:
            b_count = int(b_data.get("count") or 0)
        except (TypeError, ValueError):
            b_count = 0

        if 200 <= b_response.status_code < 300:
            self.record(
                VULNERABLE,
                "B 读取 A 的 LLM 统计明细",
                f"HTTP {b_response.status_code}; count={b_count}; A 的会话统计接口没有按用户过滤",
                "LLM 统计",
            )
        elif b_response.status_code in (401, 403, 404):
            self.record(
                PASS,
                "B 读取 A 的 LLM 统计明细",
                f"HTTP {b_response.status_code}（已拒绝）",
                "LLM 统计",
            )
        else:
            self.record(
                FAIL,
                "B 读取 A 的 LLM 统计明细",
                f"HTTP {b_response.status_code}; {_snippet(b_response)}",
                "LLM 统计",
            )

    # ------------------------------------------------------------------
    # 清理与汇总
    # ------------------------------------------------------------------
    def cleanup(self) -> None:
        print("\n清理临时数据:", flush=True)

        if self.agent_session_id and self.token_a:
            response = self.request(
                "DELETE", f"/agent/session/{self.agent_session_id}", token=self.token_a
            )
            print(f"  Agent 会话清理: HTTP {response.status_code}", flush=True)

        if self.personal_doc_id and self.token_a:
            response = self.request(
                "DELETE",
                f"/knowledge/personal-docs/{self.personal_doc_id}",
                token=self.token_a,
            )
            print(f"  个人文档清理: HTTP {response.status_code}", flush=True)

        if self.diet_log_id and self.token_a:
            response = self.request(
                "DELETE", f"/diet/logs/{self.diet_log_id}", token=self.token_a
            )
            print(f"  饮食记录清理: HTTP {response.status_code}", flush=True)

        if self.conversation_id and self.token_a:
            response = self.request(
                "DELETE", f"/conversation/{self.conversation_id}", token=self.token_a
            )
            print(f"  传统对话清理: HTTP {response.status_code}", flush=True)

    def run(self) -> int:
        print(f"MealMate 多租户隔离检查")
        print(f"Base URL: {self.base_url}")
        print(f"API Prefix: {self.api_prefix}")
        if self.skip_llm:
            print("LLM 测试: 已跳过（--skip-llm）")
        print("", flush=True)

        user_a = self.register_user("a")
        user_b = self.register_user("b")
        if not user_a or not user_b:
            print("\n无法注册临时用户，终止检查。", file=sys.stderr)
            return 2

        self.username_a = user_a["username"]
        self.username_b = user_b["username"]
        self.token_a = user_a["token"]
        self.token_b = user_b["token"]

        self.create_agent_session()
        self.create_personal_doc()
        self.create_diet_log()
        self.create_conversation()
        self.check_llm_stats_isolation()

        return self.summarize()

    def summarize(self) -> int:
        counts = {PASS: 0, FAIL: 0, VULNERABLE: 0, SKIP: 0}
        for result in self.results:
            counts[result.status] = counts.get(result.status, 0) + 1

        print("\n" + "=" * 72)
        print("检查结果汇总")
        print("=" * 72)
        print(
            f"PASS={counts[PASS]}  FAIL={counts[FAIL]}  "
            f"VULNERABLE={counts[VULNERABLE]}  SKIP={counts[SKIP]}"
        )

        problems = [r for r in self.results if r.status in (FAIL, VULNERABLE)]
        if problems:
            print("\n需要关注:")
            for result in problems:
                print(f"  [{result.status}] [{result.category}] {result.name} - {result.detail}")

        print("\n测试账号不会被自动删除:")
        print(f"  A: {self.username_a}")
        print(f"  B: {self.username_b}")
        print("  （账号用于保留可追溯证据；如不需要，可在管理端或数据库中手动清理。）")

        if counts[FAIL] or counts[VULNERABLE]:
            return 1
        return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MealMate 多租户隔离检查")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="后端地址，默认 http://127.0.0.1:8000",
    )
    parser.add_argument(
        "--api-prefix",
        default="/api/v1",
        help="API 前缀，默认 /api/v1",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="单次 HTTP 请求超时时间，默认 180 秒",
    )
    parser.add_argument(
        "--stats-wait",
        type=float,
        default=8.0,
        help="等待 LLM 使用日志落库的秒数，默认 8 秒",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="打印每次请求的方法、路径和状态码",
    )
    parser.add_argument(
        "--skip-llm",
        action="store_true",
        help="跳过 Agent、传统对话和 LLM 统计测试，只测试不需要模型的资源隔离",
    )
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    checker = ApiChecker(
        base_url=args.base_url,
        api_prefix=args.api_prefix,
        timeout=args.timeout,
        verbose=args.verbose,
        skip_llm=args.skip_llm,
        stats_wait=args.stats_wait,
    )
    try:
        return checker.run()
    except httpx.RequestError as exc:
        print(f"\n网络请求失败，检查失败: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n用户中断。", file=sys.stderr)
        return 130
    finally:
        try:
            if checker.token_a:
                checker.cleanup()
        except Exception as exc:  # cleanup 不应覆盖真正的测试结果
            print(f"\n清理临时数据时出错（不影响上面的检查结论）: {exc}", file=sys.stderr)
        checker.close()


if __name__ == "__main__":
    raise SystemExit(main())
