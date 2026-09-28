# MealMate Agent Evaluation Dataset

This directory contains the reusable Agent evaluation questions. The primary
evaluation surface is `agent_core`, not direct RAG retrieval.

## Dataset

The generator creates 280 cases:

| Suite | Cases | Purpose |
| --- | ---: | --- |
| `tool_selection` | 70 | Tool routing and tool-result grounding |
| `context_memory` | 40 | Multi-turn context and compression behavior |
| `robustness` | 30 | Empty results, failures, refusals and injection probes |
| `online_research` | 10 | Web search and deep research behavior |
| `rag` | 100 | Agent-facing knowledge-base queries |
| `cache_ablation` | 30 | Agent-facing cache request sequences |

`agent_core` selects the four Agent suites above and runs 150 cases. The `rag` and
`cache_ablation` suites remain available for later focused experiments, but
are not required for the primary Agent evaluation.

Refresh the generated data only when the case definitions change:

```bash
python -m scripts.generate_agent_eval_dataset
```

The generator also writes `agent_bad_cases_v1.jsonl`, containing 16 candidate
regression probes. They become confirmed bad cases only after a run supplies
actual behavior, `run_id`, `trace_id`, and a root cause.

## Primary Comparison

The default run compares the current Agent behavior with the optimized
evaluation profile in one command. The dataset, account and repeat settings
are identical for both profiles:

```bash
python -m tests.agent_eval_runner \
  --base-url http://127.0.0.1:8000 \
  --username YOUR_TEST_USER \
  --suite agent_core \
  --include-network \
  --config-hash auto \
  --output tests/evaluation_results
```

`baseline` uses the current default system prompt. `optimized` adds explicit
tool routing, context-constraint preservation and controlled tool-failure
handling instructions. This is the change being compared; the runner does
not pretend that changing only an experiment name is an optimization.

The runner saves both raw evidence and a summary:

```text
tests/evaluation_results/agent_baseline.jsonl
tests/evaluation_results/agent_baseline.summary.json
tests/evaluation_results/agent_optimized.jsonl
tests/evaluation_results/agent_optimized.summary.json
tests/evaluation_results/agent_baseline_vs_optimized.comparison.json
```

The terminal report and comparison JSON include:

- task proxy pass rate and Agent run success rate
- tool selection accuracy, expected-tool presence and forbidden-tool violation
- tool execution success, tool-call completion and tool failure rate
- average tool calls, LLM calls and Agent iterations
- input, output and total token usage
- time to first token and total duration
- per-category and per-tool breakdowns

Raw records include the selected profile, SSE events, tool calls, tool results,
`run_id`, `trace_id`, status, errors, latency and usage fields when the backend
provides them. The current comparison does not claim a context-compression
improvement: the optimized profile changes Agent routing and failure handling,
not the compression algorithm. Token totals are available as a usage proxy;
actual money cost requires a model price table, which is not configured yet.

The runner supports checkpointed resume by default. After each complete case,
the corresponding raw JSONL file is atomically updated. If the process stops,
rerun the same command and completed cases are skipped; an incomplete case is
rerun as a whole. Baseline and optimized profiles resume independently. Use
`--no-resume` only when every selected case must be executed again from the
beginning:

```bash
python -m tests.agent_eval_runner \
  --base-url http://127.0.0.1:8000 \
  --username YOUR_TEST_USER \
  --suite agent_core \
  --include-network \
  --config-hash auto \
  --no-resume \
  --output tests/evaluation_results
```

To run only one profile, provide an experiment ID:

```bash
python -m tests.agent_eval_runner \
  --base-url http://127.0.0.1:8000 \
  --username YOUR_TEST_USER \
  --suite agent_core \
  --experiment-id agent_single \
  --profile optimized \
  --config-hash auto \
  --output tests/evaluation_results
```

Online cases are skipped unless `--include-network` is supplied.

## Optional Suites

Run the direct knowledge-base and cache cases only when doing a RAG-focused
experiment:

```bash
python -m tests.agent_eval_runner \
  --base-url http://127.0.0.1:8000 \
  --username YOUR_TEST_USER \
  --suite rag \
  --experiment-id agent_rag_probe \
  --config-hash auto \
  --output tests/evaluation_results
```

Use `--suite all` only when all 280 cases are intentionally required. Use
`--suite bad_cases` after a fix to rerun the 16 regression probes:

```bash
python -m tests.agent_eval_runner \
  --base-url http://127.0.0.1:8000 \
  --username YOUR_TEST_USER \
  --suite bad_cases \
  --experiment-id bad_cases_after_fix \
  --config-hash auto \
  --output tests/evaluation_results
```

These tests provide deterministic diagnostics. Final answer quality and bad
case root causes still require reviewing the saved answer, trace and tool
arguments.
