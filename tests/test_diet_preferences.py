import pytest

from app.diet.preference_mapping import normalize_preference_updates


def test_normalizes_compatibility_aliases():
    result = normalize_preference_updates(
        {
            "dietary_restrictions": ["low_carb_dinner"],
            "goal": "fat_loss",
            "goal_description": "减脂，晚餐尽量少碳水",
            "preferred_foods": ["chicken"],
            "disliked_foods": ["sugary_drinks"],
        }
    )

    assert result == {
        "diet_tags": ["low_carb_dinner"],
        "health_goal": "fat_loss",
        "goal_note": "减脂，晚餐尽量少碳水",
        "preferred_foods": ["chicken"],
        "avoided_foods": ["sugary_drinks"],
    }


def test_canonical_field_wins_over_alias():
    result = normalize_preference_updates(
        {
            "dietary_restrictions": ["old_tag"],
            "diet_tags": ["new_tag"],
            "goal": "old_goal",
            "health_goal": "new_goal",
        }
    )

    assert result == {"diet_tags": ["new_tag"], "health_goal": "new_goal"}


def test_rejects_unknown_fields():
    with pytest.raises(ValueError, match="不支持的饮食偏好字段"):
        normalize_preference_updates({"unknown_field": ["value"]})


def test_drops_none_values():
    assert normalize_preference_updates({"allergies": None}) == {}