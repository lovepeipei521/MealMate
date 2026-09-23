CREATE TABLE IF NOT EXISTS public.evaluation_user_settings (
    user_id varchar(255) PRIMARY KEY,
    enabled boolean NOT NULL DEFAULT true,
    sample_rate double precision NOT NULL DEFAULT 1.0
        CHECK (sample_rate >= 0.0 AND sample_rate <= 1.0),
    created_at timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP
);

COMMENT ON TABLE public.evaluation_user_settings
IS '用户级 RAG 自动评估运行时设置';
