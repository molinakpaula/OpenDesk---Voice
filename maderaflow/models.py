"""Typed request models shared by the API and support service."""

from typing import Literal

from pydantic import BaseModel


LanguageCode = Literal["en", "es", "pt"]


class SupportRequest(BaseModel):
    """Context supplied by the voice layer, beginning with a caller ID."""

    caller_id: str
    lot_id: str | None = None
    intent: str | None = None
    language: LanguageCode | None = None
