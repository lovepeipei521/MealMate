/*
 Agent Messages Tool Fields Migration

 Adds tool metadata columns for tool call/result storage.
*/

ALTER TABLE "public"."agent_messages"
ADD COLUMN IF NOT EXISTS "tool_calls" jsonb,
ADD COLUMN IF NOT EXISTS "tool_call_id" varchar(128),
ADD COLUMN IF NOT EXISTS "tool_name" varchar(128);

COMMENT ON COLUMN "public"."agent_messages"."tool_calls" IS 'Tool call payloads for assistant tool-call messages';
COMMENT ON COLUMN "public"."agent_messages"."tool_call_id" IS 'Tool call id for tool result messages';
COMMENT ON COLUMN "public"."agent_messages"."tool_name" IS 'Tool name for tool result messages';
