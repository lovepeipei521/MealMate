-- Add fields that were previously exposed by the API/tool but missing from storage.
-- Safe to run multiple times on PostgreSQL 9.6+.

ALTER TABLE IF EXISTS public.user_food_preferences
    ADD COLUMN IF NOT EXISTS preferred_foods jsonb,
    ADD COLUMN IF NOT EXISTS allergies jsonb,
    ADD COLUMN IF NOT EXISTS favorite_cuisines jsonb,
    ADD COLUMN IF NOT EXISTS calorie_goal integer,
    ADD COLUMN IF NOT EXISTS protein_goal real,
    ADD COLUMN IF NOT EXISTS fat_goal real,
    ADD COLUMN IF NOT EXISTS carbs_goal real;

COMMENT ON COLUMN public.user_food_preferences.allergies IS '用户过敏原列表';
COMMENT ON COLUMN public.user_food_preferences.favorite_cuisines IS '用户喜爱的菜系列表';
COMMENT ON COLUMN public.user_food_preferences.calorie_goal IS '每日卡路里目标';
COMMENT ON COLUMN public.user_food_preferences.protein_goal IS '每日蛋白质目标(克)';
COMMENT ON COLUMN public.user_food_preferences.fat_goal IS '每日脂肪目标(克)';
COMMENT ON COLUMN public.user_food_preferences.carbs_goal IS '每日碳水目标(克)';
COMMENT ON COLUMN public.user_food_preferences.preferred_foods IS 'User preferred foods';
