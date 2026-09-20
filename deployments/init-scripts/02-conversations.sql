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

 Date: 23/12/2025 23:30:04
*/


-- ----------------------------
-- Table structure for conversations
-- ----------------------------
DROP TABLE IF EXISTS "public"."conversations";
CREATE TABLE "public"."conversations" (
  "id" uuid NOT NULL DEFAULT uuid_generate_v4(),
  "created_at" timestamp(6) NOT NULL DEFAULT now(),
  "updated_at" timestamp(6) NOT NULL DEFAULT now(),
  "user_id" varchar(255) COLLATE "pg_catalog"."default",
  "title" varchar(255) COLLATE "pg_catalog"."default",
  "metadata" jsonb,
  "compressed_summary" text COLLATE "pg_catalog"."default",
  "compressed_message_count" int4 NOT NULL DEFAULT 0
)
;
ALTER TABLE "public"."conversations" OWNER TO "cookhero";

-- ----------------------------
-- Indexes structure for table conversations
-- ----------------------------
CREATE INDEX "ix_conversations_user_id" ON "public"."conversations" USING btree (
  "user_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_conversations_user_updated" ON "public"."conversations" USING btree (
  "user_id" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST,
  "updated_at" "pg_catalog"."timestamp_ops" ASC NULLS LAST
);

-- ----------------------------
-- Triggers structure for table conversations
-- ----------------------------
CREATE TRIGGER "update_conversations_updated_at" BEFORE UPDATE ON "public"."conversations"
FOR EACH ROW
EXECUTE PROCEDURE "public"."update_updated_at_column"();

-- ----------------------------
-- Primary Key structure for table conversations
-- ----------------------------
ALTER TABLE "public"."conversations" ADD CONSTRAINT "conversations_pkey" PRIMARY KEY ("id");
