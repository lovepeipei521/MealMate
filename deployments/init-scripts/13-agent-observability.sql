-- Agent run and per-call tracing identifiers.

ALTER TABLE IF EXISTS public.agent_messages
    ADD COLUMN IF NOT EXISTS run_id varchar(36);
CREATE INDEX IF NOT EXISTS ix_agent_messages_run_id
    ON public.agent_messages (run_id);

ALTER TABLE IF EXISTS public.llm_usage_logs
    ADD COLUMN IF NOT EXISTS trace_id varchar(36),
    ADD COLUMN IF NOT EXISTS run_id varchar(36),
    ADD COLUMN IF NOT EXISTS span_id varchar(36);
CREATE INDEX IF NOT EXISTS ix_llm_usage_logs_trace_id
    ON public.llm_usage_logs (trace_id);
CREATE INDEX IF NOT EXISTS ix_llm_usage_logs_run_id
    ON public.llm_usage_logs (run_id);
CREATE INDEX IF NOT EXISTS ix_llm_usage_logs_span_id
    ON public.llm_usage_logs (span_id);

CREATE TABLE IF NOT EXISTS public.agent_runs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    trace_id varchar(36) NOT NULL,
    run_id varchar(36) NOT NULL UNIQUE,
    user_id varchar(255),
    session_id uuid,
    agent_name varchar(100) NOT NULL DEFAULT 'default',
    status varchar(20) NOT NULL DEFAULT 'running',
    started_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at timestamp,
    duration_ms integer,
    ttft_ms integer,
    iteration_count integer NOT NULL DEFAULT 0,
    llm_call_count integer NOT NULL DEFAULT 0,
    tool_call_count integer NOT NULL DEFAULT 0,
    subagent_call_count integer NOT NULL DEFAULT 0,
    tool_failure_count integer NOT NULL DEFAULT 0,
    input_tokens integer NOT NULL DEFAULT 0,
    output_tokens integer NOT NULL DEFAULT 0,
    total_tokens integer NOT NULL DEFAULT 0,
    error_type varchar(255),
    error_message text,
    source varchar(32) NOT NULL DEFAULT 'online',
    experiment_id varchar(128),
    dataset_case_id varchar(128),
    repeat_index integer,
    config_hash varchar(128),
    trace jsonb,
    created_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_agent_runs_trace_id ON public.agent_runs (trace_id);
CREATE INDEX IF NOT EXISTS ix_agent_runs_user_id ON public.agent_runs (user_id);
CREATE INDEX IF NOT EXISTS ix_agent_runs_session_id ON public.agent_runs (session_id);
CREATE INDEX IF NOT EXISTS ix_agent_runs_status ON public.agent_runs (status);
CREATE INDEX IF NOT EXISTS ix_agent_runs_experiment_id ON public.agent_runs (experiment_id);
CREATE INDEX IF NOT EXISTS ix_agent_runs_dataset_case_id ON public.agent_runs (dataset_case_id);
CREATE INDEX IF NOT EXISTS ix_agent_runs_config_hash ON public.agent_runs (config_hash);
CREATE INDEX IF NOT EXISTS ix_agent_runs_trace_run ON public.agent_runs (trace_id, run_id);
CREATE INDEX IF NOT EXISTS ix_agent_runs_user_started ON public.agent_runs (user_id, started_at);
