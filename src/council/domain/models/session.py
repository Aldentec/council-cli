from __future__ import annotations

from typing import TypedDict


class HistoryEntry(TypedDict):
    speaker: str
    role: str
    content: str
