# app/diet/preference_mapping.py
"""Normalize diet preference inputs into persisted database fields."""

from collections.abc import Mapping
from typing import Any


PREFERENCE_ALIASES = {
    "dietary_restrictions": "diet_tags",
    "disliked_foods": "avoided_foods",
}

PREFERENCE_DB_FIELDS = frozenset(
    {
        "common_foods",
        "preferred_foods",
        "avoided_foods",
        "diet_tags",
        "allergies",
        "favorite_cuisines",
        "calorie_goal",
        "protein_goal",
        "fat_goal",
        "carbs_goal",
        "avg_daily_calories_min",
        "avg_daily_calories_max",
        "deviation_patterns",
        "stats",
    }
)


def normalize_preference_updates(data: Mapping[str, Any]) -> dict[str, Any]:
    """Map public preference names to database fields and reject unknown input."""
    normalized: dict[str, Any] = {}
    alias_values: dict[str, Any] = {}

    for key, value in data.items():
        if value is None:
            continue

        canonical_key = PREFERENCE_ALIASES.get(key, key)
        if canonical_key not in PREFERENCE_DB_FIELDS:
            raise ValueError(f"不支持的饮食偏好字段: {key}")

        if key in PREFERENCE_ALIASES:
            alias_values.setdefault(canonical_key, value)
        else:
            normalized[canonical_key] = value

    # A canonical field wins over its compatibility alias.
    for key, value in alias_values.items():
        normalized.setdefault(key, value)

    return normalized