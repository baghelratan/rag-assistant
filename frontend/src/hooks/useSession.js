import { useState, useCallback, useEffect, useRef } from 'react';
import { createSession, getSessions, getSession, deleteSession as apiDeleteSession } from '../services/api';

/**
 * useSession — Custom hook for session management
 */
export function useSession() {
  const [sessions, setSessions] = useState([]);
  const [currentSession, setCurrentSession] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const initializedRef = useRef(false);

  /* ── Load Sessions ─────────────────────────────────────────────────────── */
  const loadSessions = useCallback(async () => {
    try {
      const data = await getSessions();
      const list = Array.isArray(data) ? data : (data?.sessions || []);
      setSessions(list);
      return list;
    } catch (err) {
      console.warn('Failed to load sessions:', err.message);
      return [];
    }
  }, []);

  /* ── Create Session ────────────────────────────────────────────────────── */
  const newSession = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const session = await createSession();
      setCurrentSession(session);
      setMessages([]);
      setSessions((prev) => [session, ...prev]);
      return session;
    } catch (err) {
      console.warn('Failed to create session:', err.message);
      // Fall back to local session
      const localSession = {
        id: `local-${Date.now()}`,
        created_at: new Date().toISOString(),
        title: 'New Chat',
      };
      setCurrentSession(localSession);
      setMessages([]);
      setSessions((prev) => [localSession, ...prev]);
      return localSession;
    } finally {
      setLoading(false);
    }
  }, []);

  /* ── Select Session ────────────────────────────────────────────────────── */
  const selectSession = useCallback(async (id) => {
    setLoading(true);
    setError(null);
    try {
      const session = await getSession(id);
      setCurrentSession(session);
      const msgs = session?.messages || [];
      setMessages(msgs);
    } catch (err) {
      setError(err.message);
      // Find from local list
      const local = sessions.find((s) => s.id === id);
      if (local) {
        setCurrentSession(local);
        setMessages([]);
      }
    } finally {
      setLoading(false);
    }
  }, [sessions]);

  /* ── Delete Session ────────────────────────────────────────────────────── */
  const deleteSession = useCallback(async (id) => {
    try {
      await apiDeleteSession(id);
    } catch (_) {}
    setSessions((prev) => prev.filter((s) => s.id !== id));
    if (currentSession?.id === id) {
      setCurrentSession(null);
      setMessages([]);
    }
  }, [currentSession]);

  /* ── Add Message (local state) ──────────────────────────────────────────── */
  const addMessage = useCallback((role, content, metadata = {}) => {
    const msg = {
      id: `msg-${Date.now()}-${Math.random().toString(36).slice(2)}`,
      role,
      content,
      metadata,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, msg]);

    // Update session title from first user message
    if (role === 'user') {
      setSessions((prev) =>
        prev.map((s) =>
          s.id === currentSession?.id
            ? { ...s, title: content.slice(0, 60) || s.title }
            : s
        )
      );
    }
    return msg;
  }, [currentSession]);

  /* ── Update last assistant message (during streaming) ───────────────────── */
  const updateLastMessage = useCallback((content, metadata = {}) => {
    setMessages((prev) => {
      const updated = [...prev];
      const lastIdx = updated.length - 1;
      if (lastIdx >= 0 && updated[lastIdx].role === 'assistant') {
        updated[lastIdx] = { ...updated[lastIdx], content, metadata: { ...updated[lastIdx].metadata, ...metadata } };
      }
      return updated;
    });
  }, []);

  /* ── Auto-init session ──────────────────────────────────────────────────── */
  useEffect(() => {
    if (initializedRef.current) return;
    initializedRef.current = true;

    (async () => {
      const list = await loadSessions();
      if (list.length > 0) {
        await selectSession(list[0].id);
      } else {
        await newSession();
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return {
    sessions,
    currentSession,
    messages,
    loading,
    error,
    loadSessions,
    createSession: newSession,
    selectSession,
    deleteSession,
    addMessage,
    updateLastMessage,
    setMessages,
  };
}
