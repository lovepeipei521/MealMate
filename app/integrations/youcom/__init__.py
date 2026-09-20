# app/integrations/youcom/__init__.py
"""
You.com API integration for CookHero.
Provides Search and Research API clients.
"""

from app.integrations.youcom.client import YoucomClient, youcom_client

__all__ = ["YoucomClient", "youcom_client"]
