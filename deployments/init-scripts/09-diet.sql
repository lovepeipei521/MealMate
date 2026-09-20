-- Diet module schema
-- Tables: diet_plan_meals, diet_log_items, user_food_preferences

DROP TABLE IF EXISTS "public"."diet_log_items";
DROP TABLE IF EXISTS "public"."diet_plan_meals";
DROP TABLE IF EXISTS "public"."user_food_preferences";

-- ==============================
-- Table: diet_plan_meals
-- Planned meals within a weekly plan
-- ==============================
CREATE TABLE "public"."diet_plan_meals" (
    "id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "user_id" varchar(255) NOT NULL,
    "plan_date" date NOT NULL,
    "meal_type" varchar(20) NOT NULL,
    "dishes" jsonb,
    "total_calories" real,
    "total_protein" real,
    "total_fat" real,
    "total_carbs" real,
    "notes" text,
    "created_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "diet_plan_meals_pkey" PRIMARY KEY ("id")
);

COMMENT ON TABLE "public"."diet_plan_meals" IS '计划餐次表，存储用户每周计划的餐次详情';
COMMENT ON COLUMN "public"."diet_plan_meals"."user_id" IS '用户ID';
COMMENT ON COLUMN "public"."diet_plan_meals"."plan_date" IS '计划日期';
COMMENT ON COLUMN "public"."diet_plan_meals"."meal_type" IS '餐次类型: breakfast/lunch/dinner/snack';
COMMENT ON COLUMN "public"."diet_plan_meals"."dishes" IS '菜品列表JSON数组';

CREATE INDEX "ix_diet_plan_meals_user_date"
    ON "public"."diet_plan_meals" ("user_id", "plan_date");
CREATE INDEX "ix_diet_plan_meals_user_date_meal"
    ON "public"."diet_plan_meals" ("user_id", "plan_date", "meal_type");

-- ==============================
-- Table: diet_log_items
-- Individual food items logged by user
-- ==============================
CREATE TABLE "public"."diet_log_items" (
    "id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "log_id" uuid NOT NULL,
    "user_id" varchar(255) NOT NULL,
    "log_date" date NOT NULL,
    "meal_type" varchar(20) NOT NULL,
    "plan_meal_id" uuid,
    "food_name" varchar(255) NOT NULL,
    "weight_g" real,
    "unit" varchar(50),
    "calories" real,
    "protein" real,
    "fat" real,
    "carbs" real,
    "source" varchar(20) NOT NULL DEFAULT 'manual',
    "confidence_score" real,
    "notes" text,
    "created_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "diet_log_items_pkey" PRIMARY KEY ("id"),
    CONSTRAINT "diet_log_items_plan_meal_id_fkey" FOREIGN KEY ("plan_meal_id")
        REFERENCES "public"."diet_plan_meals" ("id") ON DELETE SET NULL
);

COMMENT ON TABLE "public"."diet_log_items" IS '饮食记录项表，存储用户记录的具体食物';
COMMENT ON COLUMN "public"."diet_log_items"."log_id" IS '日志批次ID，同一次记录的所有食物共享此ID';
COMMENT ON COLUMN "public"."diet_log_items"."user_id" IS '用户ID';
COMMENT ON COLUMN "public"."diet_log_items"."log_date" IS '记录日期';
COMMENT ON COLUMN "public"."diet_log_items"."meal_type" IS '餐次类型';
COMMENT ON COLUMN "public"."diet_log_items"."plan_meal_id" IS '关联的计划餐次ID';
COMMENT ON COLUMN "public"."diet_log_items"."food_name" IS '食物名称';
COMMENT ON COLUMN "public"."diet_log_items"."source" IS '数据来源: manual/ai_text/ai_image';
COMMENT ON COLUMN "public"."diet_log_items"."confidence_score" IS 'AI识别置信度';

CREATE INDEX "ix_diet_log_items_log_id"
    ON "public"."diet_log_items" ("log_id");
CREATE INDEX "ix_diet_log_items_user_date"
    ON "public"."diet_log_items" ("user_id", "log_date");
CREATE INDEX "ix_diet_log_items_user_date_meal"
    ON "public"."diet_log_items" ("user_id", "log_date", "meal_type");

-- ==============================
-- Table: user_food_preferences
-- User food preferences for personalization
-- ==============================
CREATE TABLE "public"."user_food_preferences" (
    "id" uuid NOT NULL DEFAULT gen_random_uuid(),
    "user_id" varchar(255) NOT NULL,
    "common_foods" jsonb,
    "avoided_foods" jsonb,
    "diet_tags" jsonb,
    "avg_daily_calories_min" integer,
    "avg_daily_calories_max" integer,
    "deviation_patterns" jsonb,
    "stats" jsonb,
    "created_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" timestamp(6) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "user_food_preferences_pkey" PRIMARY KEY ("id")
);

COMMENT ON TABLE "public"."user_food_preferences" IS '用户饮食偏好表，用于个性化推荐和学习';
COMMENT ON COLUMN "public"."user_food_preferences"."user_id" IS '用户ID，唯一';
COMMENT ON COLUMN "public"."user_food_preferences"."common_foods" IS '常见食物列表及其频率';
COMMENT ON COLUMN "public"."user_food_preferences"."avoided_foods" IS '用户避免的食物';
COMMENT ON COLUMN "public"."user_food_preferences"."diet_tags" IS '饮食标签: vegetarian, low-carb 等';
COMMENT ON COLUMN "public"."user_food_preferences"."deviation_patterns" IS '偏差模式，分析用户实际与计划的偏差';
COMMENT ON COLUMN "public"."user_food_preferences"."stats" IS '统计信息';

CREATE UNIQUE INDEX "ix_user_food_preferences_user"
    ON "public"."user_food_preferences" ("user_id");
