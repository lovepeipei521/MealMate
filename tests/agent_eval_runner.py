#!/usr/bin/env python3
"""Run the multi-suite Agent evaluation dataset through the HTTP API.

This runner records raw evidence and conservative deterministic checks. It
does not claim that keyword coverage equals answer quality. By default it runs
the same cases through the baseline and optimized Agent prompt profiles and
writes a comparison summary.
"""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Optional

try:
    import httpx
except ModuleNotFoundError:  # pragma: no cover - exercised on minimal local envs
    httpx = None  # type: ignore[assignment]


class AgentEvaluationRunner:
    def __init__(
        self,
        *,
        base_url: str,
        api_prefix: str,
        token: str,
        timeout: float,
        verbose: bool,
        experiment_id: str,
        config_hash: str,
        include_network: bool,
        evaluation_profile: str | None,
    ) -> None:
        self.api_prefix = "/" + api_prefix.strip("/")
        self.token = token
        self.timeout = timeout
        self.verbose = verbose
        self.experiment_id = experiment_id
        self.config_hash = config_hash
        self.include_network = include_network
        self.evaluation_profile = evaluation_profile
        self.client = httpx.Client(
            base_url=base_url.rstrip("/"),
            timeout=httpx.Timeout(timeout, connect=min(timeout, 10.0)),
        )

    def close(self) -> None:
        self.client.close()

    def api(self, path: str) -> str:
        return f"{self.api_prefix}/{path.lstrip('/')}"

    def request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        headers = dict(kwargs.pop("headers", {}) or {})
        headers["Authorization"] = f"Bearer {self.token}"
        if self.verbose:
            print(f"    -> {method.upper()} {self.api(path)}", flush=True)
        response = self.client.request(method, self.api(path), headers=headers, **kwargs)
        if self.verbose:
            print(f"       HTTP {response.status_code}", flush=True)
        return response

    @staticmethod
    def json_body(response: httpx.Response) -> dict[str, Any]:
        try:
            value = response.json()
        except ValueError:
            return {}
        return value if isinstance(value, dict) else {}

    def run_chat(
        self,
        *,
        question: str,
        case_id: str,
        repeat_index: int,
        session_id: Optional[str] = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        events: list[dict[str, Any]] = []
        payload: dict[str, Any] = {
            "message": question,
            "stream": True,
            "source": "evaluation",
            "experiment_id": self.experiment_id,
            "dataset_case_id": case_id,
            "repeat_index": repeat_index,
            "config_hash": self.config_hash,
            "evaluation_profile": self.evaluation_profile,
        }
        if session_id:
            payload["session_id"] = session_id
        try:
            with self.client.stream(
                "POST",
                self.api("/agent/chat"),
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Accept": "text/event-stream",
                    "Content-Type": "application/json",
                },
                json=payload,
            ) as response:
                status_code = response.status_code
                if status_code == 200:
                    for line in response.iter_lines():
                        if not line.startswith("data:"):
                            continue
                        try:
                            event = json.loads(line[5:].strip())
                        except json.JSONDecodeError:
                            continue
                        if isinstance(event, dict):
                            events.append(event)
                else:
                    body = response.read().decode("utf-8", errors="replace")[:500]
                    return {
                        "http_status": status_code,
                        "error": body,
                        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    }
        except httpx.RequestError as exc:
            return {
                "http_status": None,
                "error": str(exc),
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }

        session_event = next((e for e in events if e.get("type") == "session"), {})
        done_event = next((e for e in reversed(events) if e.get("type") == "done"), {})
        error_event = next((e for e in events if e.get("type") == "error"), {})
        text = "".join(
            str(e.get("content", ""))
            for e in events
            if e.get("type") == "text"
        )
        tool_calls = [
            e.get("name")
            for e in events
            if e.get("type") == "tool_call" and e.get("name")
        ]
        tool_results = [
            {
                "name": e.get("name"),
                "success": e.get("success"),
                "error": e.get("error"),
            }
            for e in events
            if e.get("type") == "tool_result"
        ]
        return {
            "http_status": 200,
            "session_id": done_event.get("session_id") or session_event.get("session_id"),
            "run_id": done_event.get("run_id") or session_event.get("run_id"),
            "trace_id": done_event.get("trace_id") or session_event.get("trace_id"),
            "answer": text,
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "events": events,
            "error": error_event.get("error") if error_event else None,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
        }

    def get_run(
        self,
        run_id: Optional[str],
        *,
        wait_for_compression: bool = False,
        compression_timeout: float = 45.0,
    ) -> dict[str, Any]:
        if not run_id:
            return {}
        last_response: Optional[httpx.Response] = None
        deadline = time.perf_counter() + (compression_timeout if wait_for_compression else 0)
        attempt = 0
        while True:
            attempt += 1
            response = self.request("GET", f"/agent/run/{run_id}")
            last_response = response
            if response.status_code == 200:
                detail = self.json_body(response)
                if not wait_for_compression or self.compression_event(detail):
                    return detail
                if time.perf_counter() >= deadline:
                    return detail
            elif not wait_for_compression and attempt >= 3:
                break
            elif wait_for_compression and time.perf_counter() >= deadline:
                break
            time.sleep(min(0.25 * attempt, 2.0))
        return {
            "http_status": last_response.status_code if last_response else None,
            "error": last_response.text[:500] if last_response else "run lookup failed",
        }

    @staticmethod
    def compression_event(run: dict[str, Any]) -> dict[str, Any] | None:
        """Return the persisted compression event for one Agent run."""
        for event in reversed(run.get("trace") or []):
            if isinstance(event, dict) and event.get("event_type") == "context_compression":
                return event
        return None

    @staticmethod
    def materialize_turns(case: dict[str, Any]) -> list[dict[str, Any]]:
        """Expand marked memory cases so the async compressor is exercised."""
        turns = case.get("turns")
        if not isinstance(turns, list) or not turns:
            return [{"role": "user", "content": case["question"]}]

        probe = case.get("compression_probe") or {}
        if not probe.get("run_with_long_history") or len(turns) >= 18:
            return turns

        # Each turn produces a user and an assistant message. Eighteen turns
        # cross both profile thresholds while keeping the JSONL dataset compact.
        prefix = turns[:-1]
        final_turn = turns[-1]
        filler_count = max(0, 18 - len(turns))
        fillers = [
            {
                "role": "user",
                "content": (
                    f"这是上下文测试中的第 {index} 轮普通交流，请简短确认已经记录，"
                    "不要新增饮食限制。"
                ),
            }
            for index in range(1, filler_count + 1)
        ]
        return prefix + fillers + [final_turn]

    @staticmethod
    def deterministic_checks(case: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
        observed = set(result.get("tool_calls") or [])
        expected = set(case.get("expected_tools") or [])
        forbidden = set(case.get("forbidden_tools") or [])
        answer = str(result.get("answer") or "").lower()
        facts = [str(fact) for fact in case.get("expected_facts") or []]
        found_facts = [fact for fact in facts if fact.lower() in answer]
        return {
            "expected_tools_present": sorted(expected & observed) == sorted(expected),
            "forbidden_tools_absent": not bool(forbidden & observed),
            "observed_tools": sorted(observed),
            "missing_tools": sorted(expected - observed),
            "forbidden_tools_observed": sorted(forbidden & observed),
            "keyword_coverage": (len(found_facts) / len(facts)) if facts else None,
            "found_facts": found_facts,
            "answer_non_empty": bool(result.get("answer")),
            "case_pass": (
                result.get("http_status") == 200
                and bool(result.get("answer"))
                and sorted(expected & observed) == sorted(expected)
                and not bool(forbidden & observed)
            ),
        }

    @staticmethod
    def run_metrics(record: dict[str, Any]) -> dict[str, Any]:
        """Extract Agent-specific metrics from one completed HTTP run."""
        result = record.get("result") or {}
        run = record.get("run") or {}
        checks = record.get("checks") or {}
        tool_calls = result.get("tool_calls") or []
        tool_results = result.get("tool_results") or []
        successful_tool_results = sum(
            1 for item in tool_results if item.get("success") is True
        )
        failed_tool_results = sum(
            1 for item in tool_results if item.get("success") is False
        )
        run_status = run.get("status")
        compression = AgentEvaluationRunner.compression_event(run)
        is_final_turn = bool(record.get("is_final_turn"))
        expected_facts = [
            str(fact) for fact in record.get("case", {}).get("expected_facts") or []
        ]
        answer = str(result.get("answer") or "").lower()
        found_memory_facts = [
            fact for fact in expected_facts if fact.lower() in answer
        ]
        return {
            "run_status": run_status,
            "run_succeeded": run_status == "succeeded",
            "tool_selection_eligible": bool(
                record.get("case", {}).get("expected_tools")
                or record.get("case", {}).get("forbidden_tools")
            ),
            "tool_selection_correct": bool(
                checks.get("expected_tools_present")
                and checks.get("forbidden_tools_absent")
            ),
            "expected_tool_present": bool(checks.get("expected_tools_present")),
            "forbidden_tool_used": bool(checks.get("forbidden_tools_observed")),
            "tool_call_count": len(tool_calls),
            "tool_result_count": len(tool_results),
            "successful_tool_result_count": successful_tool_results,
            "failed_tool_result_count": failed_tool_results,
            "tool_execution_success": (
                successful_tool_results / len(tool_results) if tool_results else None
            ),
            "tool_call_completion": (
                len(tool_results) / len(tool_calls) if tool_calls else None
            ),
            "llm_call_count": run.get("llm_call_count"),
            "iteration_count": run.get("iteration_count"),
            "input_tokens": run.get("input_tokens"),
            "output_tokens": run.get("output_tokens"),
            "total_tokens": run.get("total_tokens"),
            "ttft_ms": run.get("ttft_ms"),
            "duration_ms": run.get("duration_ms") or result.get("latency_ms"),
            "compression_observed": compression is not None,
            "compression_triggered": bool(compression and compression.get("triggered")),
            "compression_succeeded": bool(
                compression and compression.get("status") == "success"
            ),
            "compressed_messages": (
                compression.get("messages_compressed") if compression else None
            ),
            "compression_duration_ms": (
                compression.get("duration_ms") if compression else None
            ),
            "compression_input_tokens": (
                compression.get("compression_input_tokens") if compression else None
            ),
            "compression_output_tokens": (
                compression.get("compression_output_tokens") if compression else None
            ),
            "compression_total_tokens": (
                compression.get("compression_total_tokens") if compression else None
            ),
            "compression_before_uncompressed_messages": (
                compression.get("uncompressed_count_before") if compression else None
            ),
            "compression_after_uncompressed_messages": (
                compression.get("uncompressed_count_after") if compression else None
            ),
            "compression_fallback_used": bool(
                compression and compression.get("fallback_used")
            ),
            "compression_profile": compression.get("profile") if compression else None,
            "memory_retention_eligible": (
                record.get("category") == "context_memory"
                and is_final_turn
                and bool(expected_facts)
            ),
            "memory_fact_coverage": (
                len(found_memory_facts) / len(expected_facts) if expected_facts else None
            ),
        }

    def should_skip(self, case: dict[str, Any]) -> Optional[str]:
        if case.get("requires_network") and not self.include_network:
            return "requires --include-network"
        return None

    def run_case(self, case: dict[str, Any], repeat_index: int) -> list[dict[str, Any]]:
        skip_reason = self.should_skip(case)
        if skip_reason:
            return [{
                "case_id": case["case_id"],
                "category": case["category"],
                "repeat_index": repeat_index,
                "status": "skipped",
                "skip_reason": skip_reason,
            }]

        turns = self.materialize_turns(case)
        records: list[dict[str, Any]] = []
        session_id: Optional[str] = None
        previous_record: Optional[dict[str, Any]] = None
        for turn_index, turn in enumerate(turns):
            question = str(turn.get("content") or turn.get("question") or case["question"])
            result = self.run_chat(
                question=question,
                case_id=case["case_id"],
                repeat_index=repeat_index,
                session_id=session_id,
            )
            session_id = result.get("session_id") or session_id
            run_detail = self.get_run(
                result.get("run_id"),
                wait_for_compression=bool(
                    (case.get("compression_probe") or {}).get("run_with_long_history")
                ),
            )
            if previous_record and previous_record.get("metrics", {}).get(
                "compression_triggered"
            ):
                previous_record["metrics"]["agent_input_tokens_after_compression"] = (
                    run_detail.get("input_tokens")
                )
            record = {
                "case_id": case["case_id"],
                "category": case["category"],
                "repeat_index": repeat_index,
                "evaluation_profile": self.evaluation_profile,
                "turn_index": turn_index,
                "is_final_turn": turn_index == len(turns) - 1,
                "question": question,
                "expected_cache": turn.get("expected_cache"),
                "status": "completed" if result.get("http_status") == 200 else "failed",
                "case": case,
                "result": result,
                "run": run_detail,
                "checks": self.deterministic_checks(case, result),
            }
            record["metrics"] = self.run_metrics(record)
            records.append(record)
            previous_record = record
        return records


    def run(self, cases: list[dict[str, Any]], repeats: int) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        total = len(cases) * repeats
        completed = 0
        for case in cases:
            for repeat_index in range(repeats):
                completed += 1
                print(f"[{completed}/{total}] {case['case_id']}", flush=True)
                records.extend(self.run_case(case, repeat_index))
        return records


SUITE_CATEGORIES: dict[str, set[str]] = {
    # Agent-facing behavior is the default evaluation surface. Direct RAG
    # retrieval metrics remain an optional specialist suite.
    "agent_core": {"tool_selection", "context_memory", "robustness", "online_research"},
    "rag": {"rag", "cache_ablation"},
    "all": set(),
    "bad_cases": set(),
}

DEFAULT_DATASET = "tests/evaluation_datasets/agent_eval_v1.jsonl"
BAD_CASE_DATASET = "tests/evaluation_datasets/agent_bad_cases_v1.jsonl"


def load_cases(path: Path, categories: set[str]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                case = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {path}:{line_number}: {exc}") from exc
            if not categories or case.get("category") in categories:
                cases.append(case)
    return cases


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def aggregate_agent_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate quality, tool, efficiency and token metrics for a profile."""
    completed = [record for record in records if record.get("status") == "completed"]
    attempted = [record for record in records if record.get("status") != "skipped"]
    metrics = [record.get("metrics", {}) for record in completed]
    selection_records = [
        metric for metric in metrics if metric.get("tool_selection_eligible")
    ]
    expected_tool_records = [
        record.get("metrics", {})
        for record in completed
        if record.get("case", {}).get("expected_tools")
    ]
    forbidden_tool_records = [
        record.get("metrics", {})
        for record in completed
        if record.get("case", {}).get("forbidden_tools")
    ]
    tool_results = [
        item
        for record in completed
        for item in (record.get("result", {}).get("tool_results") or [])
    ]
    tool_calls = [
        str(name)
        for record in completed
        for name in (record.get("result", {}).get("tool_calls") or [])
        if name
    ]

    tools: dict[str, dict[str, Any]] = {}
    for name in sorted(set(tool_calls) | {str(item.get("name")) for item in tool_results}):
        if name == "None":
            continue
        calls = sum(1 for item in tool_calls if item == name)
        results = [item for item in tool_results if str(item.get("name")) == name]
        successes = sum(1 for item in results if item.get("success") is True)
        tools[name] = {
            "calls": calls,
            "results": len(results),
            "successes": successes,
            "execution_success_rate": successes / len(results) if results else None,
        }

    def values(key: str) -> list[float]:
        return [
            float(metric[key])
            for metric in metrics
            if metric.get(key) is not None
        ]

    keyword_values = [
        float((record.get("checks") or {}).get("keyword_coverage"))
        for record in completed
        if (record.get("checks") or {}).get("keyword_coverage") is not None
    ]

    compression_records = [
        metric for metric in metrics if metric.get("compression_observed")
    ]
    compression_triggered = [
        metric for metric in compression_records if metric.get("compression_triggered")
    ]
    compression_successful = [
        metric for metric in compression_triggered if metric.get("compression_succeeded")
    ]
    retention_records = [
        metric
        for metric in metrics
        if metric.get("memory_retention_eligible")
        and metric.get("memory_fact_coverage") is not None
    ]

    def metric_values(items: list[dict[str, Any]], key: str) -> list[float]:
        return [float(item[key]) for item in items if item.get(key) is not None]

    compression_metrics = {
        "available": bool(compression_records),
        "records": len(compression_records),
        "triggered_records": len(compression_triggered),
        "successful_records": len(compression_successful),
        "trigger_rate": (
            len(compression_triggered) / len(compression_records)
            if compression_records else None
        ),
        "success_rate": (
            len(compression_successful) / len(compression_triggered)
            if compression_triggered else None
        ),
        "mean_compressed_messages": _mean(
            metric_values(compression_successful, "compressed_messages")
        ),
        "mean_compression_duration_ms": _mean(
            metric_values(compression_successful, "compression_duration_ms")
        ),
        "mean_compression_input_tokens": _mean(
            metric_values(compression_successful, "compression_input_tokens")
        ),
        "mean_compression_output_tokens": _mean(
            metric_values(compression_successful, "compression_output_tokens")
        ),
        "mean_compression_total_tokens": _mean(
            metric_values(compression_successful, "compression_total_tokens")
        ),
        "mean_agent_input_tokens_before_compression": _mean(
            metric_values(compression_successful, "input_tokens")
        ),
        "mean_agent_input_tokens_after_compression": _mean(
            metric_values(compression_successful, "agent_input_tokens_after_compression")
        ),
        "memory_constraint_retention_rate": _mean(
            metric_values(retention_records, "memory_fact_coverage")
        ),
        "memory_retention_records": len(retention_records),
    }

    return {
        "evaluated_records": len(completed),
        "skipped_records": len(records) - len(attempted),
        "request_success_rate": len(completed) / len(attempted) if attempted else None,
        "run_success_rate": (
            sum(bool(metric.get("run_succeeded")) for metric in metrics) / len(metrics)
            if metrics else None
        ),
        "task_proxy_pass_rate": (
            sum(bool((record.get("checks") or {}).get("case_pass")) for record in completed)
            / len(completed)
            if completed else None
        ),
        "answer_non_empty_rate": (
            sum(bool((record.get("checks") or {}).get("answer_non_empty")) for record in completed)
            / len(completed)
            if completed else None
        ),
        "mean_keyword_coverage": _mean(keyword_values),
        "tool_selection_accuracy": (
            sum(bool(metric.get("tool_selection_correct")) for metric in selection_records)
            / len(selection_records)
            if selection_records else None
        ),
        "expected_tool_presence_rate": (
            sum(bool(metric.get("expected_tool_present")) for metric in expected_tool_records)
            / len(expected_tool_records)
            if expected_tool_records else None
        ),
        "forbidden_tool_violation_rate": (
            sum(bool(metric.get("forbidden_tool_used")) for metric in forbidden_tool_records)
            / len(forbidden_tool_records)
            if forbidden_tool_records else None
        ),
        "tool_execution_success_rate": (
            sum(item.get("success") is True for item in tool_results) / len(tool_results)
            if tool_results else None
        ),
        "tool_call_completion_rate": (
            sum(metric.get("tool_result_count", 0) for metric in metrics)
            / sum(metric.get("tool_call_count", 0) for metric in metrics)
            if sum(metric.get("tool_call_count", 0) for metric in metrics) else None
        ),
        "tool_failure_rate": (
            sum(item.get("success") is False for item in tool_results) / len(tool_results)
            if tool_results else None
        ),
        "mean_tool_calls_per_run": _mean(values("tool_call_count")),
        "mean_llm_calls_per_run": _mean(values("llm_call_count")),
        "mean_iterations_per_run": _mean(values("iteration_count")),
        "mean_input_tokens_per_run": _mean(values("input_tokens")),
        "mean_output_tokens_per_run": _mean(values("output_tokens")),
        "mean_total_tokens_per_run": _mean(values("total_tokens")),
        "mean_ttft_ms": _mean(values("ttft_ms")),
        "mean_duration_ms": _mean(values("duration_ms")),
        "total_input_tokens": sum(values("input_tokens")),
        "total_output_tokens": sum(values("output_tokens")),
        "total_tokens": sum(values("total_tokens")),
        "tools": tools,
        "compression_metrics": compression_metrics,
        "cost_metrics": {
            "available": False,
            "reason": "已记录 token，但项目当前没有统一的模型价格表，无法直接计算金额成本。",
        },
    }


def login(client: httpx.Client, api_prefix: str, username: str, password: str) -> str:
    response = client.post(
        f"/{api_prefix.strip('/')}/auth/login",
        json={"username": username, "password": password},
    )
    if response.status_code != 200:
        raise RuntimeError(f"login failed: HTTP {response.status_code} {response.text[:300]}")
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("login response did not contain access_token")
    return str(token)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run MealMate Agent evaluation JSONL")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--api-prefix", default="/api/v1")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument(
        "--suite",
        choices=tuple(SUITE_CATEGORIES),
        default="agent_core",
        help="agent_core is the default; rag and all are optional broader suites",
    )
    parser.add_argument("--category", action="append", default=[], help="repeatable category filter")
    auth = parser.add_mutually_exclusive_group(required=True)
    auth.add_argument("--username")
    auth.add_argument("--token")
    parser.add_argument(
        "--compare",
        action="store_true",
        help="run baseline and optimized profiles in one command (default when no experiment id is given)",
    )
    parser.add_argument(
        "--experiment-id",
        default=None,
        help="single-run experiment name; omit it to compare baseline vs optimized",
    )
    parser.add_argument(
        "--profile",
        choices=("baseline", "optimized"),
        default="optimized",
        help="profile for a single run",
    )
    parser.add_argument("--config-hash", default="manual")
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--include-network", action="store_true")
    parser.add_argument("--timeout", type=float, default=240.0)
    parser.add_argument("--output", default="tests/evaluation_results")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    compare = args.compare or not args.experiment_id
    if args.compare and args.experiment_id:
        raise SystemExit("--compare 不能与 --experiment-id 同时使用")
    if args.repeat < 1:
        raise SystemExit("--repeat must be at least 1")
    dataset_value = BAD_CASE_DATASET if args.suite == "bad_cases" and args.dataset == DEFAULT_DATASET else args.dataset
    dataset = Path(dataset_value)
    categories = set(args.category)
    if not categories:
        categories = SUITE_CATEGORIES[args.suite].copy()
    cases = load_cases(dataset, categories)
    if args.limit > 0:
        cases = cases[: args.limit]
    if not cases:
        raise SystemExit("No evaluation cases selected")
    if httpx is None:
        raise SystemExit(
            "当前 Python 环境缺少 httpx。请先激活项目 .venv，或执行 "
            "python -m pip install -r requirements.txt。"
        )

    bootstrap_client = httpx.Client(
        base_url=args.base_url.rstrip("/"),
        timeout=httpx.Timeout(args.timeout, connect=min(args.timeout, 10.0)),
    )
    try:
        token = args.token or login(
            bootstrap_client,
            args.api_prefix,
            args.username,
            getpass.getpass("登录密码: "),
        )
    finally:
        bootstrap_client.close()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    base_config_hash = args.config_hash
    if base_config_hash == "auto":
        base_config_hash = hashlib.sha256(Path("config.yml").read_bytes()).hexdigest()[:16]

    def run_profile(profile: str, experiment_id: str) -> tuple[dict[str, Any], Path]:
        profile_config_hash = f"{base_config_hash}:{profile}"
        runner = AgentEvaluationRunner(
            base_url=args.base_url,
            api_prefix=args.api_prefix,
            token=token,
            timeout=args.timeout,
            verbose=args.verbose,
            experiment_id=experiment_id,
            config_hash=profile_config_hash,
            include_network=args.include_network,
            evaluation_profile=profile,
        )
        try:
            records = runner.run(cases, args.repeat)
        finally:
            runner.close()

        stem = experiment_id.replace("/", "_").replace("\\", "_")
        result_path = output_dir / f"{stem}.jsonl"
        summary_path = output_dir / f"{stem}.summary.json"
        with result_path.open("w", encoding="utf-8", newline="\n") as handle:
            for record in records:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")

        by_category: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in records:
            by_category[str(record.get("category"))].append(record)
        completed_records = [record for record in records if record.get("status") == "completed"]
        checks = [record.get("checks", {}) for record in completed_records]
        agent_metrics = aggregate_agent_metrics(records)
        latencies = [
            float(record.get("result", {}).get("latency_ms"))
            for record in completed_records
            if record.get("result", {}).get("latency_ms") is not None
        ]
        summary: dict[str, Any] = {
            "experiment_id": experiment_id,
            "evaluation_profile": profile,
            "profile_description": (
                "当前默认 Agent 行为"
                if profile == "baseline"
                else "增加工具路由、上下文约束、失败处理和上下文压缩策略"
            ),
            "config_hash": profile_config_hash,
            "suite": args.suite,
            "dataset": str(dataset),
            "selected_categories": sorted(categories),
            "selected_cases": len(cases),
            "records": len(records),
            "status_counts": dict(Counter(record.get("status") for record in records)),
            "agent_metrics": agent_metrics,
            "answer_non_empty_rate": (
                sum(bool(check.get("answer_non_empty")) for check in checks) / len(checks)
                if checks else None
            ),
            "case_pass_rate": (
                sum(bool(check.get("case_pass")) for check in checks) / len(checks)
                if checks else None
            ),
            "mean_latency_ms": sum(latencies) / len(latencies) if latencies else None,
            "categories": {},
            "raw_result_file": str(result_path),
        }
        for category, category_records in sorted(by_category.items()):
            category_checks = [
                record.get("checks", {})
                for record in category_records
                if record.get("checks")
            ]
            keyword_values = [
                float(check["keyword_coverage"])
                for check in category_checks
                if check.get("keyword_coverage") is not None
            ]
            summary["categories"][category] = {
                "records": len(category_records),
                "agent_metrics": aggregate_agent_metrics(category_records),
                "case_pass_rate": (
                    sum(bool(check.get("case_pass")) for check in category_checks)
                    / len(category_checks)
                    if category_checks else None
                ),
                "answer_non_empty_rate": (
                    sum(bool(check.get("answer_non_empty")) for check in category_checks)
                    / len(category_checks)
                    if category_checks else None
                ),
                "tool_presence_rate": (
                    sum(bool(check.get("expected_tools_present")) for check in category_checks)
                    / len(category_checks)
                    if category_checks else None
                ),
                "forbidden_tool_rate": (
                    sum(bool(check.get("forbidden_tools_absent")) for check in category_checks)
                    / len(category_checks)
                    if category_checks else None
                ),
                "mean_keyword_coverage": (
                    sum(keyword_values) / len(keyword_values) if keyword_values else None
                ),
            }
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return summary, result_path

    if compare:
        summaries: dict[str, dict[str, Any]] = {}
        result_files: dict[str, str] = {}
        for profile in ("baseline", "optimized"):
            summary, result_path = run_profile(profile, f"agent_{profile}")
            summaries[profile] = summary
            result_files[profile] = str(result_path)

        def delta(metric: str) -> float | None:
            before = summaries["baseline"].get(metric)
            after = summaries["optimized"].get(metric)
            if before is None or after is None:
                return None
            return after - before

        def agent_delta(metric: str) -> float | None:
            before = summaries["baseline"]["agent_metrics"].get(metric)
            after = summaries["optimized"]["agent_metrics"].get(metric)
            if before is None or after is None:
                return None
            return after - before

        comparison = {
            "comparison_id": "agent_baseline_vs_optimized",
            "suite": args.suite,
            "dataset": str(dataset),
            "selected_cases": len(cases),
            "protocol": "同一账号、同一数据集、同一 repeat 设置，先跑 baseline，再跑 optimized",
            "what_changed": (
                "optimized 请求附加 Agent 工具路由、上下文约束、工具失败处理策略，"
                "并使用更早的滚动上下文压缩和硬约束摘要提示；"
                "baseline 使用当前默认 Agent 提示词和原有 10/20 消息压缩策略。"
            ),
            "profiles": summaries,
            "metric_deltas_optimized_minus_baseline": {
                "case_pass_rate": delta("case_pass_rate"),
                "answer_non_empty_rate": delta("answer_non_empty_rate"),
                "mean_latency_ms": delta("mean_latency_ms"),
                "mean_keyword_coverage": agent_delta("mean_keyword_coverage"),
                "task_proxy_pass_rate": agent_delta("task_proxy_pass_rate"),
                "tool_selection_accuracy": agent_delta("tool_selection_accuracy"),
                "expected_tool_presence_rate": agent_delta("expected_tool_presence_rate"),
                "forbidden_tool_violation_rate": agent_delta("forbidden_tool_violation_rate"),
                "tool_execution_success_rate": agent_delta("tool_execution_success_rate"),
                "tool_call_completion_rate": agent_delta("tool_call_completion_rate"),
                "mean_llm_calls_per_run": agent_delta("mean_llm_calls_per_run"),
                "mean_tool_calls_per_run": agent_delta("mean_tool_calls_per_run"),
                "mean_iterations_per_run": agent_delta("mean_iterations_per_run"),
                "mean_total_tokens_per_run": agent_delta("mean_total_tokens_per_run"),
                "mean_input_tokens_per_run": agent_delta("mean_input_tokens_per_run"),
                "mean_output_tokens_per_run": agent_delta("mean_output_tokens_per_run"),
                "mean_ttft_ms": agent_delta("mean_ttft_ms"),
                "mean_duration_ms": agent_delta("mean_duration_ms"),
            },
            "compression_metric_deltas_optimized_minus_baseline": {
                key: (
                    summaries["optimized"]["agent_metrics"]["compression_metrics"].get(key)
                    - summaries["baseline"]["agent_metrics"]["compression_metrics"].get(key)
                    if summaries["optimized"]["agent_metrics"]["compression_metrics"].get(key) is not None
                    and summaries["baseline"]["agent_metrics"]["compression_metrics"].get(key) is not None
                    else None
                )
                for key in (
                    "trigger_rate",
                    "success_rate",
                    "mean_compressed_messages",
                    "mean_compression_duration_ms",
                    "mean_compression_input_tokens",
                    "mean_compression_output_tokens",
                    "mean_compression_total_tokens",
                    "mean_agent_input_tokens_before_compression",
                    "mean_agent_input_tokens_after_compression",
                    "memory_constraint_retention_rate",
                )
            },
            "raw_result_files": result_files,
        }
        comparison_path = output_dir / "agent_baseline_vs_optimized.comparison.json"
        comparison_path.write_text(
            json.dumps(comparison, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        def format_value(value: Any, kind: str) -> str:
            if value is None:
                return "-"
            number = float(value)
            if kind == "rate":
                return f"{number:.2%}"
            if kind == "ms":
                return f"{number:.0f} ms"
            if kind == "count":
                return f"{number:.0f}"
            return f"{number:.1f}"

        def format_delta(value: Any, kind: str) -> str:
            if value is None:
                return "-"
            number = float(value)
            if kind == "rate":
                return f"{number:+.2%}"
            if kind == "ms":
                return f"{number:+.0f} ms"
            if kind == "count":
                return f"{number:+.0f}"
            return f"{number:+.1f}"

        def print_metric(key: str, label: str, kind: str) -> None:
            baseline_value = summaries["baseline"]["agent_metrics"].get(key)
            optimized_value = summaries["optimized"]["agent_metrics"].get(key)
            difference = comparison["metric_deltas_optimized_minus_baseline"].get(key)
            print(
                f"{label:<30}"
                f"{format_value(baseline_value, kind):>14}"
                f"{format_value(optimized_value, kind):>14}"
                f"{format_delta(difference, kind):>14}"
            )

        def print_compression_metric(key: str, label: str, kind: str) -> None:
            baseline_metrics = summaries["baseline"]["agent_metrics"]["compression_metrics"]
            optimized_metrics = summaries["optimized"]["agent_metrics"]["compression_metrics"]
            baseline_value = baseline_metrics.get(key)
            optimized_value = optimized_metrics.get(key)
            difference = comparison["compression_metric_deltas_optimized_minus_baseline"].get(key)
            print(
                f"{label:<38}"
                f"{format_value(baseline_value, kind):>14}"
                f"{format_value(optimized_value, kind):>14}"
                f"{format_delta(difference, kind):>14}"
            )

        print("\n" + "=" * 72)
        print("MealMate Agent 评测对比结果")
        print("=" * 72)
        print(f"数据集: {dataset} | 评测用例数: {len(cases)} | suite: {args.suite}")
        print(
            "实际请求记录: "
            f"baseline={summaries['baseline']['records']} | "
            f"optimized={summaries['optimized']['records']}"
        )
        print("优化项: 工具路由、上下文约束、工具失败处理、上下文压缩策略")
        print("差值定义: optimized - baseline")
        print("-" * 72)
        print(f"{'指标':<30}{'baseline':>14}{'optimized':>14}{'差值':>14}")
        print("-" * 72)
        print("任务效果")
        for key, label, kind in (
            ("task_proxy_pass_rate", "任务代理通过率", "rate"),
            ("run_success_rate", "Agent 运行成功率", "rate"),
            ("answer_non_empty_rate", "非空回答率", "rate"),
            ("mean_keyword_coverage", "关键词覆盖率（粗略）", "rate"),
        ):
            print_metric(key, label, kind)

        print("-" * 72)
        print("工具选择与执行")
        for key, label, kind in (
            ("tool_selection_accuracy", "工具选择正确率", "rate"),
            ("expected_tool_presence_rate", "期望工具调用率", "rate"),
            ("forbidden_tool_violation_rate", "禁止工具误调用率", "rate"),
            ("tool_execution_success_rate", "工具执行成功率", "rate"),
            ("tool_call_completion_rate", "工具调用完成率", "rate"),
            ("tool_failure_rate", "工具失败率", "rate"),
            ("mean_tool_calls_per_run", "平均工具调用次数", "number"),
        ):
            print_metric(key, label, kind)

        print("-" * 72)
        print("Agent 效率与 Token")
        for key, label, kind in (
            ("mean_llm_calls_per_run", "平均 LLM 调用次数", "number"),
            ("mean_iterations_per_run", "平均 Agent 循环次数", "number"),
            ("mean_input_tokens_per_run", "平均输入 Token", "count"),
            ("mean_output_tokens_per_run", "平均输出 Token", "count"),
            ("mean_total_tokens_per_run", "平均总 Token", "count"),
            ("mean_ttft_ms", "平均首 Token 延迟", "ms"),
            ("mean_duration_ms", "平均总耗时", "ms"),
        ):
            print_metric(key, label, kind)

        print("-" * 72)
        print("分类任务代理通过率")
        print(f"{'分类':<30}{'baseline':>14}{'optimized':>14}{'差值':>14}")
        for category in sorted(categories):
            baseline_value = summaries["baseline"]["categories"].get(category, {}).get("agent_metrics", {}).get("task_proxy_pass_rate")
            optimized_value = summaries["optimized"]["categories"].get(category, {}).get("agent_metrics", {}).get("task_proxy_pass_rate")
            category_delta = (
                optimized_value - baseline_value
                if baseline_value is not None and optimized_value is not None
                else None
            )
            print(
                f"{category:<30}"
                f"{format_value(baseline_value, 'rate'):>14}"
                f"{format_value(optimized_value, 'rate'):>14}"
                f"{format_delta(category_delta, 'rate'):>14}"
            )

        all_tools = sorted(
            set(summaries["baseline"]["agent_metrics"].get("tools", {}))
            | set(summaries["optimized"]["agent_metrics"].get("tools", {}))
        )
        if all_tools:
            print("-" * 72)
            print("按工具执行情况")
            print(f"{'工具':<30}{'baseline 调用/成功率':>22}{'optimized 调用/成功率':>22}")
            for tool_name in all_tools:
                baseline_tool = summaries["baseline"]["agent_metrics"].get("tools", {}).get(tool_name, {})
                optimized_tool = summaries["optimized"]["agent_metrics"].get("tools", {}).get(tool_name, {})
                baseline_text = f"{baseline_tool.get('calls', 0)} / {format_value(baseline_tool.get('execution_success_rate'), 'rate')}"
                optimized_text = f"{optimized_tool.get('calls', 0)} / {format_value(optimized_tool.get('execution_success_rate'), 'rate')}"
                print(f"{tool_name:<30}{baseline_text:>22}{optimized_text:>22}")

        print("-" * 72)
        print("上下文压缩")
        print(f"{'指标':<38}{'baseline':>14}{'optimized':>14}{'差值':>14}")
        for key, label, kind in (
            ("trigger_rate", "压缩触发率", "rate"),
            ("success_rate", "压缩成功率", "rate"),
            ("mean_compressed_messages", "平均每次压缩消息数", "number"),
            ("mean_compression_duration_ms", "平均压缩耗时", "ms"),
            ("mean_compression_input_tokens", "压缩 LLM 平均输入 Token", "count"),
            ("mean_compression_output_tokens", "压缩 LLM 平均输出 Token", "count"),
            ("mean_compression_total_tokens", "压缩 LLM 平均总 Token", "count"),
            ("mean_agent_input_tokens_before_compression", "压缩前 Agent 输入 Token", "count"),
            ("mean_agent_input_tokens_after_compression", "压缩后 Agent 输入 Token", "count"),
            ("memory_constraint_retention_rate", "关键约束保持率（粗略）", "rate"),
        ):
            print_compression_metric(key, label, kind)
        print("说明: 压缩后 Agent 输入 Token 需要下一轮对话才能观测；末轮可能为空。")
        print("Token: 已显示 Agent run 的输入、输出和总 Token；实际金额成本需要配置各模型价格表，目前未计算。")
        print(f"详细对比文件: {comparison_path}")
        print(f"baseline 原始记录: {result_files['baseline']}")
        print(f"optimized 原始记录: {result_files['optimized']}")
        print("=" * 72)
    else:
        summary, _ = run_profile(args.profile, args.experiment_id)
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
