from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class Message:
    message_id: str
    session_id: str
    role: str
    content: str
    created_at: str


@dataclass(slots=True)
class MemoryState:
    session_id: str
    profile: dict[str, Any] = field(default_factory=dict)
    conversation_summary: str = ""
    active_topic: str = ""
    active_goals: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    decision_stage: str = ""
    last_report_brief: str = ""
    updated_at: str = ""


@dataclass(slots=True)
class RuntimeContext:
    session_id: str
    latest_user_message: str
    recent_messages: list[Message] = field(default_factory=list)
    profile: dict[str, Any] = field(default_factory=dict)
    conversation_summary: str = ""
    active_topic: str = ""
    active_goals: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    decision_stage: str = ""
    last_report_brief: str = ""
