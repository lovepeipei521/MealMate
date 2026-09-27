#!/usr/bin/env python3
"""End-to-end smoke check for persisted Agent run observability.

Example:
    python -m tests.agent_observability_check --base-url http://127.0.0.1:8000 --username YOUR_USERNAME

The script creates one Agent session and run. It does not create or delete users.
"""

from __future__ import annotations

import argparse
import getpass
import json
import sys
import uuid
from typing import Any, Iterable, Optional

import httpx


class AgentObservabilityCheck:
    def __init__(
        self,
        *,
        base_url: str,
        api_prefix: str,
        timeout: float,
        verbose: bool,
        message: str,
        other_token: Optional[str],
    ) -> None:
        self.api_prefix = "/" + api_prefix.strip("/")
        self.verbose = verbose
        self.message = message
        self.other_token = other_token
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
        )
        self.passes = 0
        self.failures = 0
        self.skips = 0
        self.token: Optional[str] = None

    def close(self) -> None:
        self.client.close()

    def check(self, name: str, passed: bool, detail: str = "") -> bool:
        status = "PASS" if passed else "FAIL"
        line = f"[{status}] {name}"
        if detail:
            line += f" - {detail}"
        print(line, flush=True)
        if passed:
            self.passes += 1
        else:
            self.failures += 1
        return passed

    def skip(self, name: str, detail: str) -> None:
        self.skips += 1
        print(f"[SKIP] {name} - {detail}", flush=True)

    def api(self, path: str) -> str:
        return f"{self.api_prefix}/{path.lstrip('/')}"

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
        response = self.client.request(
            method,
            self.api(path),
            headers=headers,
            **kwargs,
        )
        if self.verbose:
            print(f"       HTTP {response.status_code}", flush=True)
        return response

    @staticmethod
    def response_json(response: httpx.Response) -> dict[str, Any]:
        try:
            value = response.json()
        except ValueError:
            return {}
        return value if isinstance(value, dict) else {}

    @staticmethod
    def snippet(response: httpx.Response, limit: int = 240) -> str:
        body = response.text.replace("\n", " ").strip()
        return body if len(body) <= limit else body[:limit] + "..."

    def login(self, username: str, password: str) -> bool:
        response = self.request(
            "POST",
            "/auth/login",
            json={"username": username, "password": password},
        )
        if response.status_code != 200:
            return self.check(
                "登录测试账号",
                False,
                f"HTTP {response.status_code}; {self.snippet(response)}",
            )

        token = self.response_json(response).get("access_token")
        if not token:
            return self.check("登录测试账号", False, "响应中没有 access_token")
        self.token = str(token)
        return self.check("登录测试账号", True, "HTTP 200")

    @staticmethod
    def is_uuid(value: Any) -> bool:
        try:
            uuid.UUID(str(value))
            return True
        except (ValueError, TypeError, AttributeError):
            return False

    def send_streaming_chat(self) -> tuple[Optional[str], Optional[str], Optional[str]]:
        events: list[dict[str, Any]] = []
        try:
            with self.client.stream(
                "POST",
                self.api("/agent/chat"),
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "text/event-stream",
                    "Content-Type": "application/json",
                },
                json={"message": self.message, "stream": True},
            ) as response:
                if response.status_code != 200:
                    body = response.read().decode("utf-8", errors="replace")
                    self.check(
                        "Agent 流式对话请求",
                        False,
                        f"HTTP {response.status_code}; {body[:240]}",
                    )
                    return None, None, None
                self.check("Agent 流式对话请求", True, "HTTP 200")

                header_trace_id = response.headers.get("X-Trace-Id")
                header_run_id = response.headers.get("X-Run-Id")
                for line in response.iter_lines():
                    if not line.startswith("data:"):
                        continue
                    payload = line[5:].strip()
                    try:
                        event = json.loads(payload)
                    except json.JSONDecodeError:
                        self.check("解析 SSE 事件", False, payload[:160])
                        continue
                    if isinstance(event, dict):
                        events.append(event)
        except httpx.RequestError as exc:
            self.check("Agent 流式对话请求", False, str(exc))
            return None, None, None

        session_event = next(
            (event for event in events if event.get("type") == "session"), {}
        )
        text_events = [
            event
            for event in events
            if event.get("type") == "text"
            and isinstance(event.get("content"), str)
            and event["content"]
        ]
        done_event = next(
            (event for event in reversed(events) if event.get("type") == "done"), {}
        )
        error_event = next(
            (event for event in events if event.get("type") == "error"), None
        )

        self.check("收到 SSE session 事件", bool(session_event))
        self.check(
            "收到非空 SSE 文本分片",
            bool(text_events),
            f"文本分片数={len(text_events)}; 字符数={sum(len(event['content']) for event in text_events)}",
        )
        self.check("收到 SSE done 事件", bool(done_event))
        if error_event:
            self.check(
                "Agent 执行无错误事件",
                False,
                str(error_event.get("error", error_event))[:200],
            )

        session_id = session_event.get("session_id")
        run_id = done_event.get("run_id") or session_event.get("run_id") or header_run_id
        trace_id = (
            done_event.get("trace_id")
            or session_event.get("trace_id")
            or header_trace_id
        )

        self.check("SSE 包含 session_id", bool(session_id))
        self.check("run_id 是 UUID", self.is_uuid(run_id), str(run_id or "缺失"))
        self.check("trace_id 是 UUID", self.is_uuid(trace_id), str(trace_id or "缺失"))
        self.check(
            "HTTP 响应头与 SSE run_id 一致",
            bool(header_run_id and run_id == header_run_id),
            f"header={header_run_id}; event={run_id}",
        )
        self.check(
            "HTTP 响应头与 SSE trace_id 一致",
            bool(header_trace_id and trace_id == header_trace_id),
            f"header={header_trace_id}; event={trace_id}",
        )
        if session_id:
            print(f"    session_id={session_id}", flush=True)
        if run_id:
            print(f"    run_id={run_id}", flush=True)
        if trace_id:
            print(f"    trace_id={trace_id}", flush=True)
        return (
            str(run_id) if run_id else None,
            str(trace_id) if trace_id else None,
            str(session_id) if session_id else None,
        )

    def check_run_detail(self, run_id: str, trace_id: str) -> None:
        response = self.request("GET", f"/agent/run/{run_id}", token=self.token)
        if response.status_code != 200:
            self.check(
                "读取 Agent run 详情",
                False,
                f"HTTP {response.status_code}; {self.snippet(response)}",
            )
            return

        run = self.response_json(response)
        self.check("读取 Agent run 详情", True, "HTTP 200")
        self.check("详情 run_id 匹配", run.get("run_id") == run_id)
        self.check("详情 trace_id 匹配", run.get("trace_id") == trace_id)
        self.check(
            "Agent run 状态为 succeeded",
            run.get("status") == "succeeded",
            f"status={run.get('status')}; error={run.get('error_message')}",
        )

        llm_call_count = run.get("llm_call_count")
        self.check(
            "记录到至少一次 LLM 调用",
            isinstance(llm_call_count, int) and llm_call_count > 0,
            f"llm_call_count={llm_call_count}",
        )
        trace = run.get("trace")
        trace = trace if isinstance(trace, list) else []
        actions = {
            (item.get("event_type"), item.get("action"))
            for item in trace
            if isinstance(item, dict)
        }
        self.check(
            "trace 包含 run 开始和结束",
            ("run", "run_start") in actions and ("run", "run_end") in actions,
            f"trace_events={len(trace)}",
        )
        self.check(
            "trace 包含 LLM 调用记录",
            any(event_type == "llm_call" for event_type, _ in actions),
        )

    def check_run_list(self, run_id: str, session_id: str) -> None:
        response = self.request(
            "GET",
            "/agent/runs",
            token=self.token,
            params={"session_id": session_id},
        )
        if response.status_code != 200:
            self.check(
                "读取当前用户 Agent run 列表",
                False,
                f"HTTP {response.status_code}; {self.snippet(response)}",
            )
            return

        runs = self.response_json(response).get("runs")
        runs = runs if isinstance(runs, list) else []
        found = any(
            isinstance(run, dict) and run.get("run_id") == run_id for run in runs
        )
        self.check(
            "当前用户 run 列表包含本次 run",
            found,
            f"返回记录数={len(runs)}",
        )

    def check_other_user_isolation(self, run_id: str, session_id: str) -> None:
        if not self.other_token:
            self.skip("跨用户 run 隔离", "未提供 --other-token")
            return

        detail = self.request(
            "GET", f"/agent/run/{run_id}", token=self.other_token
        )
        self.check(
            "其他用户不能读取此 run 详情",
            detail.status_code in (403, 404),
            f"HTTP {detail.status_code}",
        )

        listing = self.request(
            "GET",
            "/agent/runs",
            token=self.other_token,
            params={"session_id": session_id},
        )
        if listing.status_code != 200:
            self.check(
                "其他用户 run 列表请求",
                False,
                f"HTTP {listing.status_code}; {self.snippet(listing)}",
            )
            return
        runs = self.response_json(listing).get("runs")
        runs = runs if isinstance(runs, list) else []
        found = any(
            isinstance(run, dict) and run.get("run_id") == run_id for run in runs
        )
        self.check("其他用户列表不包含此 run", not found)

    def run(self) -> int:
        print("MealMate Agent 可观测性端到端检查", flush=True)
        print(f"API: {self.client.base_url}{self.api_prefix}", flush=True)

        run_id, trace_id, session_id = self.send_streaming_chat()
        if run_id and trace_id and session_id:
            self.check_run_detail(run_id, trace_id)
            self.check_run_list(run_id, session_id)
            self.check_other_user_isolation(run_id, session_id)
        elif run_id or trace_id or session_id:
            self.check(
                "SSE 返回完整的 session/run/trace 标识",
                False,
                f"session_id={session_id}; run_id={run_id}; trace_id={trace_id}",
            )

        print("\n检查汇总", flush=True)
        print(
            f"PASS={self.passes}  FAIL={self.failures}  SKIP={self.skips}",
            flush=True,
        )
        print("本脚本会在该账号下保留本次 Agent 会话和 run 记录。", flush=True)
        return 1 if self.failures else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="MealMate Agent 可观测性端到端检查")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="后端地址，默认 http://127.0.0.1:8000",
    )
    parser.add_argument("--api-prefix", default="/api/v1", help="API 前缀")
    parser.add_argument("--timeout", type=float, default=180.0, help="请求超时秒数")
    auth = parser.add_mutually_exclusive_group(required=True)
    auth.add_argument("--username", help="已有测试账号；密码会安全地交互输入")
    auth.add_argument("--token", help="已有 Bearer Token")
    parser.add_argument(
        "--other-token",
        help="可选：另一用户的 Bearer Token，用于测试 run 多租户隔离",
    )
    parser.add_argument(
        "--message",
        default="请只回复 OK，不调用工具，用于 Agent 追踪测试。",
        help="发送给 Agent 的测试消息",
    )
    parser.add_argument("--verbose", action="store_true", help="打印 HTTP 请求详情")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    checker = AgentObservabilityCheck(
        base_url=args.base_url,
        api_prefix=args.api_prefix,
        timeout=args.timeout,
        verbose=args.verbose,
        message=args.message,
        other_token=args.other_token,
    )
    try:
        if args.token:
            checker.token = args.token
        elif not checker.login(args.username, getpass.getpass("登录密码: ")):
            return 1
        return checker.run()
    except httpx.RequestError as exc:
        print(f"\n网络请求失败: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\n用户中断。", file=sys.stderr)
        return 130
    finally:
        checker.close()


if __name__ == "__main__":
    raise SystemExit(main())
