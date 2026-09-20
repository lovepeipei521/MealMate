/*
 Agent Messages Timing Fields Migration

 Adds timing columns to track thinking and response duration
*/

-- Add timing columns to agent_messages
ALTER TABLE "public"."agent_messages"
ADD COLUMN IF NOT EXISTS "thinking_duration_ms" integer,
ADD COLUMN IF NOT EXISTS "answer_duration_ms" integer;

-- Comment on columns
COMMENT ON COLUMN "public"."agent_messages"."thinking_duration_ms" IS 'Duration of thinking/tool execution phase in milliseconds';
COMMENT ON COLUMN "public"."agent_messages"."answer_duration_ms" IS 'Duration of LLM response generation in milliseconds';
