"""
Session manager using aiosqlite for async SQLite-backed conversation history.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

import aiosqlite

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """A single conversation message."""
    id: str
    session_id: str
    role: str  # "user" | "assistant" | "system"
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Session:
    """A conversation session."""
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[Message] = field(default_factory=list)


_CREATE_SESSIONS_TABLE = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_CREATE_MESSAGES_TABLE = """
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata TEXT NOT NULL DEFAULT '{}',
    timestamp TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
)
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)
"""


class SessionManager:
    """
    Async SQLite-backed session and message manager.
    """

    def __init__(self) -> None:
        self._db_path = settings.SESSION_DB_PATH
        self._db: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def init(self) -> None:
        """Initialize the database and create tables."""
        import os
        os.makedirs(os.path.dirname(self._db_path) if os.path.dirname(self._db_path) else ".", exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute("PRAGMA foreign_keys=ON")
        await self._db.execute(_CREATE_SESSIONS_TABLE)
        await self._db.execute(_CREATE_MESSAGES_TABLE)
        await self._db.execute(_CREATE_INDEX)
        await self._db.commit()
        logger.info("SessionManager: database initialized at '%s'", self._db_path)

    async def close(self) -> None:
        """Close the database connection."""
        if self._db:
            await self._db.close()

    # ------------------------------------------------------------------
    # Session operations
    # ------------------------------------------------------------------

    async def create_session(self, title: str = "") -> Session:
        """Create a new conversation session."""
        session_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        title = title or f"Session {now[:10]}"

        async with self._lock:
            await self._db.execute(
                "INSERT INTO sessions (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (session_id, title, now, now),
            )
            await self._db.commit()

        logger.info("Created session '%s'", session_id)
        return Session(id=session_id, title=title, created_at=now, updated_at=now)

    async def get_session(self, session_id: str) -> Optional[Session]:
        """Retrieve a session with its message history."""
        async with self._db.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if not row:
            return None

        messages = await self.get_history(session_id)
        return Session(
            id=row["id"],
            title=row["title"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            messages=messages,
        )

    async def list_sessions(self) -> List[Session]:
        """List all sessions ordered by most recently updated."""
        async with self._db.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC"
        ) as cursor:
            rows = await cursor.fetchall()

        return [
            Session(
                id=row["id"],
                title=row["title"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages."""
        async with self._lock:
            await self._db.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            await self._db.commit()

        logger.info("Deleted session '%s'", session_id)
        return True

    async def session_exists(self, session_id: str) -> bool:
        """Check if a session exists."""
        async with self._db.execute(
            "SELECT 1 FROM sessions WHERE id = ?", (session_id,)
        ) as cursor:
            return await cursor.fetchone() is not None

    # ------------------------------------------------------------------
    # Message operations
    # ------------------------------------------------------------------

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """Add a message to a session."""
        msg_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        meta_str = json.dumps(metadata or {})

        async with self._lock:
            await self._db.execute(
                """INSERT INTO messages (id, session_id, role, content, metadata, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (msg_id, session_id, role, content, meta_str, now),
            )
            await self._db.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )
            await self._db.commit()

        return Message(
            id=msg_id,
            session_id=session_id,
            role=role,
            content=content,
            metadata=metadata or {},
            timestamp=now,
        )

    async def get_history(
        self,
        session_id: str,
        limit: int = 10,
    ) -> List[Message]:
        """
        Get the most recent messages for a session.

        Args:
            session_id: The session ID.
            limit: Maximum messages to return.

        Returns:
            List of Message objects in chronological order.
        """
        async with self._db.execute(
            """SELECT * FROM messages WHERE session_id = ?
               ORDER BY timestamp DESC LIMIT ?""",
            (session_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()

        # Reverse to get chronological order
        messages = []
        for row in reversed(rows):
            try:
                meta = json.loads(row["metadata"])
            except (json.JSONDecodeError, TypeError):
                meta = {}
            messages.append(
                Message(
                    id=row["id"],
                    session_id=row["session_id"],
                    role=row["role"],
                    content=row["content"],
                    metadata=meta,
                    timestamp=row["timestamp"],
                )
            )
        return messages
