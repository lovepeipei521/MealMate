/*
 Navicat Premium Dump SQL

 Source Server         : cookhero
 Source Server Type    : PostgreSQL
 Source Server Version : 160011 (160011)
 Source Host           : localhost:5432
 Source Catalog        : cookhero
 Source Schema         : public

 Target Server Type    : PostgreSQL
 Target Server Version : 160011 (160011)
 File Encoding         : 65001

 Date: 23/12/2025 23:30:39
*/


-- ----------------------------
-- Table structure for messages
-- ----------------------------
DROP TABLE IF EXISTS "public"."messages";
CREATE TABLE "public"."messages" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "conversation_id" uuid NOT NULL,
  "role" varchar(20) COLLATE "pg_catalog"."default" NOT NULL,
  "content" text COLLATE "pg_catalog"."default" NOT NULL,
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "sources" jsonb,
  "intent" varchar(50) COLLATE "pg_catalog"."default",
  "thinking" jsonb,
  "thinking_duration_ms" int4,
  "answer_duration_ms" int4
)
;
ALTER TABLE "public"."messages" OWNER TO "cookhero";

-- ----------------------------
-- Indexes structure for table messages
-- ----------------------------
CREATE INDEX "ix_messages_conv_created" ON "public"."messages" USING btree (
  "conversation_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_messages_conversation_id" ON "public"."messages" USING btree (
  "conversation_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table messages
-- ----------------------------
ALTER TABLE "public"."messages" ADD CONSTRAINT "messages_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Foreign Keys structure for table messages
-- ----------------------------
ALTER TABLE "public"."messages" ADD CONSTRAINT "messages_conversation_id_fkey" FOREIGN KEY ("conversation_id") REFERENCES "public"."conversations" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
