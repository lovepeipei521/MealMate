/*
 Agent Sessions Table

 Source Server         : cookhero
 Source Server Type    : PostgreSQL
 Source Schema         : public
*/

-- ----------------------------
-- Table structure for agent_sessions
-- ----------------------------
DROP TABLE IF EXISTS "public"."agent_sessions" CASCADE;
CREATE TABLE "public"."agent_sessions" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "user_id" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "title" varchar(255) COLLATE "pg_catalog"."default",
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "compressed_summary" text COLLATE "pg_catalog"."default",
  "compressed_count" int4 NOT NULL DEFAULT 0,
  "metadata" jsonb
)
;
ALTER TABLE "public"."agent_sessions" OWNER TO "cookhero";

-- ----------------------------
-- Indexes structure for table agent_sessions
-- ----------------------------
CREATE INDEX "ix_agent_sessions_user_updated" ON "public"."agent_sessions" USING btree (
  "user_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "updated_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);

-- ----------------------------
-- Triggers structure for table agent_sessions
-- ----------------------------
CREATE TRIGGER "update_agent_sessions_updated_at" BEFORE UPDATE ON "public"."agent_sessions"
FOR EACH ROW
EXECUTE PROCEDURE "public"."update_updated_at_column"();

-- ----------------------------
-- Primary Key structure for table agent_sessions
-- ----------------------------
ALTER TABLE "public"."agent_sessions" ADD CONSTRAINT "agent_sessions_pkey" PRIMARY KEY ("id");
