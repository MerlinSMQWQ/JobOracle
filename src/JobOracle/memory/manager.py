from __future__ import annotations

from pathlib import Path

from ..llm_client import EmploymentLLMClient
from .extractor import ProfileExtractor
from .models import RuntimeContext
from .store import MemoryStore
from .summarizer import MemorySummarizer


class MemoryManager:
    def __init__(self, db_path: Path, llm_client: EmploymentLLMClient | None = None):
        self.store = MemoryStore(db_path)
        self.extractor = ProfileExtractor(llm_client)
        self.summarizer = MemorySummarizer()

    def start_session(self, title: str = "新会话") -> str:
        return self.store.create_session(title)

    def ingest_user_message(self, session_id: str, content: str) -> RuntimeContext:
        self.store.append_message(session_id, "user", content)
        memory = self.store.load_memory(session_id)
        messages = self.store.list_recent_messages(session_id)
        extracted = self.extractor.extract_profile(
            content,
            existing_profile=memory.profile,
            recent_messages=[{"role": item.role, "content": item.content} for item in messages],
        )
        memory.profile = self.extractor.merge_profile(memory.profile, extracted)
        memory = self.summarizer.update(memory, messages)
        self.store.save_memory(memory)
        return self.build_runtime_context(session_id, latest_user_message=content)

    def ingest_assistant_message(self, session_id: str, content: str) -> RuntimeContext:
        self.store.append_message(session_id, "assistant", content)
        memory = self.store.load_memory(session_id)
        messages = self.store.list_recent_messages(session_id)
        memory = self.summarizer.update(memory, messages)
        self.store.save_memory(memory)
        return self.build_runtime_context(session_id)

    def build_runtime_context(self, session_id: str, latest_user_message: str = "") -> RuntimeContext:
        memory = self.store.load_memory(session_id)
        messages = self.store.list_recent_messages(session_id)
        if not latest_user_message:
            user_messages = [message.content for message in messages if message.role == "user"]
            latest_user_message = user_messages[-1] if user_messages else ""
        return RuntimeContext(
            session_id=session_id,
            latest_user_message=latest_user_message,
            recent_messages=messages,
            profile=memory.profile,
            conversation_summary=memory.conversation_summary,
            active_topic=memory.active_topic,
            active_goals=memory.active_goals,
            open_questions=memory.open_questions,
            decision_stage=memory.decision_stage,
            last_report_brief=memory.last_report_brief,
        )

    def update_last_report_brief(self, session_id: str, brief: str) -> None:
        memory = self.store.load_memory(session_id)
        memory.last_report_brief = brief.strip()
        self.store.save_memory(memory)
