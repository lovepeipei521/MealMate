-- File: 06-llm_usage_logs.sql

CREATE TABLE IF NOT EXISTS llm_usage_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_id VARCHAR(36) NOT NULL,
    module_name VARCHAR(50) NOT NULL,
    user_id VARCHAR(255),
    conversation_id UUID,
    model_name VARCHAR(100),
    input_tokens INTEGER,
    output_tokens INTEGER,
    total_tokens INTEGER,
    duration_ms INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_llm_usage_logs_request_id ON llm_usage_logs (request_id);
CREATE INDEX IF NOT EXISTS ix_llm_usage_logs_module_name ON llm_usage_logs (module_name);
CREATE INDEX IF NOT EXISTS ix_llm_usage_logs_user_id ON llm_usage_logs (user_id);
CREATE INDEX IF NOT EXISTS ix_llm_usage_logs_conversation_id ON llm_usage_logs (conversation_id);
CREATE INDEX IF NOT EXISTS ix_llm_usage_logs_model_name ON llm_usage_logs (model_name);
CREATE INDEX IF NOT EXISTS ix_llm_usage_logs_created_at ON llm_usage_logs (created_at);
CREATE INDEX IF NOT EXISTS ix_llm_usage_created_at_desc ON llm_usage_logs (created_at DESC);
CREATE INDEX IF NOT EXISTS ix_llm_usage_user_created ON llm_usage_logs (user_id, created_at);
CREATE INDEX IF NOT EXISTS ix_llm_usage_module_created ON llm_usage_logs (module_name, created_at);
CREATE INDEX IF NOT EXISTS ix_llm_usage_model_created ON llm_usage_logs (model_name, created_at);