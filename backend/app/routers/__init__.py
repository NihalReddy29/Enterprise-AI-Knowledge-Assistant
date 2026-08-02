"""API routers package."""

from app.routers import admin, auth, chat, documents, search

__all__ = ["auth", "documents", "search", "chat", "admin"]
