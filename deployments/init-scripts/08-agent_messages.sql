/*
 Agent Messages Table

 Source Server         : cookhero
 Source Server Type    : PostgreSQL
 Source Schema         : public
*/

-- ----------------------------
-- Table structure for agent_messages
-- ----------------------------
DROP TABLE IF EXISTS "public"."agent_messages";
CREATE TABLE "public"."agent_messages" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "session_id" uuid NOT NULL,
  "role" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "content" text COLLATE "pg_catalog"."default" NOT NULL,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "trace" jsonb,
  "tool_calls" jsonb,
  "tool_call_id" varchar(128) COLLATE "pg_catalog"."default",
  "tool_name" varchar(128) COLLATE "pg_catalog"."default"
)
;
ALTER TABLE "public"."agent_messages" OWNER TO "cookhero";

-- ----------------------------
-- Indexes structure for table agent_messages
-- ----------------------------
CREATE INDEX "ix_agent_messages_session_created" ON "public"."agent_messages" USING btree (
  "session_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table agent_messages
-- ----------------------------
ALTER TABLE "public"."agent_messages" ADD CONSTRAINT "agent_messages_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Foreign Keys structure for table agent_messages
-- ----------------------------
ALTER TABLE "public"."agent_messages" ADD CONSTRAINT "agent_messages_session_id_fkey" 
  FOREIGN KEY ("session_id") REFERENCES "public"."agent_sessions" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
