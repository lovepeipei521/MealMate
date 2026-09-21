# app/integrations/youcom/__init__.py
"""
You.com API integration for MealMate.
Provides Search and Research API clients.
"""

from app.integrations.youcom.client import (
    YoucomClient,
    get_youcom_client,
    youcom_client,
)

__all__ = ["YoucomClient", "get_youcom_client", "youcom_client"]
