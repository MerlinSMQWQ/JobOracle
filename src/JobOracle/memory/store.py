from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from .models import MemoryState, Message


def _utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="microseconds") + "Z"


class MemoryStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _initialize(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    message_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS memory_states (
                    session_id TEXT PRIMARY KEY,
                    profile_json TEXT NOT NULL,
                    conversation_summary TEXT NOT NULL,
                    active_topic TEXT NOT NULL,
                    active_goals_json TEXT NOT NULL,
                    open_questions_json TEXT NOT NULL,
                    decision_stage TEXT NOT NULL,
                    last_report_brief TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def create_session(self, title: str = "新会话") -> str:
        session_id = str(uuid.uuid4())
        now = _utc_now()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO sessions (session_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, title, now, now),
            )
            conn.execute(
                """
                INSERT INTO memory_states (
                    session_id, profile_json, conversation_summary, active_topic,
                    active_goals_json, open_questions_json, decision_stage,
                    last_report_brief, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, "{}", "", "", "[]", "[]", "", "", now),
            )
        return session_id

    def touch_session(self, session_id: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
                (_utc_now(), session_id),
            )

    def append_message(self, session_id: str, role: str, content: str) -> Message:
        message = Message(
            message_id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            created_at=_utc_now(),
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO messages (message_id, session_id, role, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (message.message_id, message.session_id, message.role, message.content, message.created_at),
            )
        self.touch_session(session_id)
        return message

    def list_recent_messages(self, session_id: str, limit: int = 8) -> list[Message]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT message_id, session_id, role, content, created_at
                FROM messages
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (session_id, max(1, limit)),
            ).fetchall()
        return [
            Message(
                message_id=row[0],
                session_id=row[1],
                role=row[2],
                content=row[3],
                created_at=row[4],
            )
            for row in reversed(rows)
        ]

    def load_memory(self, session_id: str) -> MemoryState:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT profile_json, conversation_summary, active_topic,
                       active_goals_json, open_questions_json, decision_stage,
                       last_report_brief, updated_at
                FROM memory_states
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"Session not found: {session_id}")
        return MemoryState(
            session_id=session_id,
            profile=json.loads(row[0]),
            conversation_summary=row[1],
            active_topic=row[2],
            active_goals=json.loads(row[3]),
            open_questions=json.loads(row[4]),
            decision_stage=row[5],
            last_report_brief=row[6],
            updated_at=row[7],
        )

    def save_memory(self, memory: MemoryState) -> None:
        memory.updated_at = _utc_now()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO memory_states (
                    session_id, profile_json, conversation_summary, active_topic,
                    active_goals_json, open_questions_json, decision_stage,
                    last_report_brief, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    profile_json = excluded.profile_json,
                    conversation_summary = excluded.conversation_summary,
                    active_topic = excluded.active_topic,
                    active_goals_json = excluded.active_goals_json,
                    open_questions_json = excluded.open_questions_json,
                    decision_stage = excluded.decision_stage,
                    last_report_brief = excluded.last_report_brief,
                    updated_at = excluded.updated_at
                """,
                (
                    memory.session_id,
                    json.dumps(memory.profile, ensure_ascii=False),
                    memory.conversation_summary,
                    memory.active_topic,
                    json.dumps(memory.active_goals, ensure_ascii=False),
                    json.dumps(memory.open_questions, ensure_ascii=False),
                    memory.decision_stage,
                    memory.last_report_brief,
                    memory.updated_at,
                ),
            )
        self.touch_session(memory.session_id)
