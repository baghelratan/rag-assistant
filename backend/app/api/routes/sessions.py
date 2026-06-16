"""
Session management API routes.
POST   /api/v1/sessions        — create session
GET    /api/v1/sessions        — list sessions
GET    /api/v1/sessions/{id}   — get session with history
DELETE /api/v1/sessions/{id}   — delete session
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.observability.metrics import ACTIVE_SESSIONS
from app.session.manager import SessionManager, Session, Message

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request/Response models
# ---------------------------------------------------------------------------

class CreateSessionRequest(BaseModel):
    title: Optional[str] = Field(default=None, max_length=200)


class MessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    metadata: dict
    timestamp: str


class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    messages: List[MessageResponse] = []


def _msg_to_response(m: Message) -> MessageResponse:
    return MessageResponse(
        id=m.id,
        session_id=m.session_id,
        role=m.role,
        content=m.content,
        metadata=m.metadata,
        timestamp=m.timestamp,
    )


def _session_to_response(s: Session) -> SessionResponse:
    return SessionResponse(
        id=s.id,
        title=s.title,
        created_at=s.created_at,
        updated_at=s.updated_at,
        messages=[_msg_to_response(m) for m in s.messages],
    )


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

def get_session_manager(request: Request) -> SessionManager:
    return request.app.state.session_manager


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/sessions", response_model=SessionResponse, status_code=201)
async def create_session(request: Request, body: CreateSessionRequest = CreateSessionRequest()):
    """Create a new conversation session."""
    sm: SessionManager = get_session_manager(request)
    session = await sm.create_session(title=body.title or "")
    ACTIVE_SESSIONS.inc()
    return _session_to_response(session)


@router.get("/sessions", response_model=List[SessionResponse])
async def list_sessions(request: Request):
    """List all conversation sessions ordered by most recently updated."""
    sm: SessionManager = get_session_manager(request)
    sessions = await sm.list_sessions()
    return [_session_to_response(s) for s in sessions]


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str, request: Request):
    """Get a specific session with its full message history."""
    sm: SessionManager = get_session_manager(request)
    session = await sm.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return _session_to_response(session)


@router.delete("/sessions/{session_id}", status_code=200)
async def delete_session(session_id: str, request: Request):
    """Delete a session and all its messages."""
    sm: SessionManager = get_session_manager(request)
    if not await sm.session_exists(session_id):
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    await sm.delete_session(session_id)
    ACTIVE_SESSIONS.dec()
    return {"session_id": session_id, "status": "deleted"}
