from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class EmploymentRequest:
    query: str
    mode: str = "auto"
    profile: dict[str, Any] = field(default_factory=dict)
    save: bool = True
    use_offerstar: bool = False
    offerstar_page_from: int = 1
    offerstar_page_to: int = 1
    offerstar_max_items: int = 20
    session_id: str | None = None
    conversation_summary: str = ""
    recent_messages: list[dict[str, str]] = field(default_factory=list)
    active_goals: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)


@dataclass(slots=True)
class EmploymentSearchResult:
    title: str
    url: str
    snippet: str
    query: str
    source: str = "search"
    published_date: str | None = None


@dataclass(slots=True)
class AgentNote:
    role: str
    content: str


@dataclass(slots=True)
class EmploymentReport:
    title: str
    mode: str
    markdown: str
    used_llm: bool
    used_search: bool = False
    search_results: list[EmploymentSearchResult] = field(default_factory=list)
    agent_notes: list[AgentNote] = field(default_factory=list)
    output_path: str | None = None
