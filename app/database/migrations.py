"""Idempotent schema upgrades for databases created by older revisions."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


_PREFERENCE_COLUMN_MIGRATIONS = (
    """
    ALTER TABLE IF EXISTS public.user_food_preferences
        ADD COLUMN IF NOT EXISTS preferred_foods jsonb,
        ADD COLUMN IF NOT EXISTS allergies jsonb,
        ADD COLUMN IF NOT EXISTS favorite_cuisines jsonb,
        ADD COLUMN IF NOT EXISTS calorie_goal integer,
        ADD COLUMN IF NOT EXISTS protein_goal real,
        ADD COLUMN IF NOT EXISTS fat_goal real,
        ADD COLUMN IF NOT EXISTS carbs_goal real
    """,
)


async def apply_compatibility_migrations(conn: AsyncConnection) -> None:
    """Apply small, additive migrations that keep existing deployments working."""
    for statement in _PREFERENCE_COLUMN_MIGRATIONS:
        await conn.execute(text(statement))