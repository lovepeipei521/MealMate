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

 Date: 13/01/2026 11:18:21
*/


-- ----------------------------
-- Table structure for rag_evaluations
-- ----------------------------
DROP TABLE IF EXISTS "public"."rag_evaluations";
CREATE TABLE "public"."rag_evaluations" (
  "id" uuid NOT NULL DEFAULT gen_random_uuid(),
  "message_id" uuid NOT NULL,
  "conversation_id" uuid NOT NULL,
  "user_id" varchar(255) COLLATE "pg_catalog"."default",
  "query" text COLLATE "pg_catalog"."default" NOT NULL,
  "rewritten_query" text COLLATE "pg_catalog"."default",
  "context" text COLLATE "pg_catalog"."default" NOT NULL,
  "response" text COLLATE "pg_catalog"."default" NOT NULL,
  "context_precision" float8,
  "context_recall" float8,
  "faithfulness" float8,
  "answer_relevancy" float8,
  "evaluation_status" varchar(20) COLLATE "pg_catalog"."default" NOT NULL DEFAULT 'pending'::character varying,
  "error_message" text COLLATE "pg_catalog"."default",
  "evaluation_duration_ms" int4,
  "created_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
  "evaluated_at" timestamp(6)
)
;
ALTER TABLE "public"."rag_evaluations" OWNER TO "cookhero";

-- ----------------------------
-- Indexes structure for table rag_evaluations
-- ----------------------------
CREATE INDEX "ix_rag_evaluations_conv_created" ON "public"."rag_evaluations" USING btree (
  "conversation_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_rag_evaluations_conversation_id" ON "public"."rag_evaluations" USING btree (
  "conversation_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_rag_evaluations_message_id" ON "public"."rag_evaluations" USING btree (
  "message_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);
CREATE INDEX "ix_rag_evaluations_status" ON "public"."rag_evaluations" USING btree (
  "evaluation_status" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_rag_evaluations_user_created" ON "public"."rag_evaluations" USING btree (
  "user_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "created_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);
CREATE INDEX "ix_rag_evaluations_user_id" ON "public"."rag_evaluations" USING btree (
  "user_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);

-- ----------------------------
-- Checks structure for table rag_evaluations
-- ----------------------------
ALTER TABLE "public"."rag_evaluations" ADD CONSTRAINT "chk_rag_evaluations_status" CHECK (evaluation_status::text = ANY (ARRAY['pending'::character varying, 'completed'::character varying, 'failed'::character varying]::text[]));

-- ----------------------------
-- Primary Key structure for table rag_evaluations
-- ----------------------------
ALTER TABLE "public"."rag_evaluations" ADD CONSTRAINT "rag_evaluations_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Foreign Keys structure for table rag_evaluations
-- ----------------------------
ALTER TABLE "public"."rag_evaluations" ADD CONSTRAINT "fk_rag_evaluations_message" FOREIGN KEY ("message_id") REFERENCES "public"."messages" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
