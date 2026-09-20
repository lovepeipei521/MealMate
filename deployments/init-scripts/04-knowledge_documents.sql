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

 Date: 23/12/2025 23:30:32
*/


-- ----------------------------
-- Table structure for knowledge_documents
-- ----------------------------
DROP TABLE IF EXISTS "public"."knowledge_documents";
CREATE TABLE "public"."knowledge_documents" (
  "id" uuid NOT NULL,
  "user_id" uuid,
  "dish_name" varchar(255) COLLATE "pg_catalog"."default" NOT NULL,
  "category" varchar(100) COLLATE "pg_catalog"."default" NOT NULL,
  "difficulty" varchar(50) COLLATE "pg_catalog"."default" NOT NULL,
  "data_source" varchar(32) COLLATE "pg_catalog"."default" NOT NULL,
  "source_type" varchar(32) COLLATE "pg_catalog"."default" NOT NULL,
  "source" varchar(512) COLLATE "pg_catalog"."default" NOT NULL,
  "is_dish_index" bool NOT NULL,
  "content" text COLLATE "pg_catalog"."default" NOT NULL,
  "created_at" timestamp(6) NOT NULL,
  "updated_at" timestamp(6) NOT NULL
)
;
ALTER TABLE "public"."knowledge_documents" OWNER TO "cookhero";

-- ----------------------------
-- Indexes structure for table knowledge_documents
-- ----------------------------
CREATE INDEX "ix_knowledge_docs_data_source" ON "public"."knowledge_documents" USING btree (
  "data_source" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_knowledge_docs_source_type" ON "public"."knowledge_documents" USING btree (
  "source_type" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_knowledge_docs_user_category" ON "public"."knowledge_documents" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST,
  "category" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_knowledge_documents_data_source" ON "public"."knowledge_documents" USING btree (
  "data_source" COLLATE "pg_catalog"."default" "pg_catalog"."text_ops" ASC NULLS LAST
);
CREATE INDEX "ix_knowledge_documents_user_id" ON "public"."knowledge_documents" USING btree (
  "user_id" "pg_catalog"."uuid_ops" ASC NULLS LAST
);

-- ----------------------------
-- Primary Key structure for table knowledge_documents
-- ----------------------------
ALTER TABLE "public"."knowledge_documents" ADD CONSTRAINT "knowledge_documents_pkey" PRIMARY KEY ("id");

-- ----------------------------
-- Foreign Keys structure for table knowledge_documents
-- ----------------------------
ALTER TABLE "public"."knowledge_documents" ADD CONSTRAINT "knowledge_documents_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users" ("id") ON DELETE CASCADE ON UPDATE NO ACTION;
