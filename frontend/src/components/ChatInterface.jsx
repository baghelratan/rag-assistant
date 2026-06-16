import React, { useState, useRef, useEffect, useCallback } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import SessionSidebar from './SessionSidebar';
import SourceCitations from './SourceCitations';
import { useStream } from '../hooks/useStream';
import { useSession } from '../hooks/useSession';
import { useToast } from './Toast';

/* ─── Suggestion Cards ─────────────────────────────────────────────────────── */
const SUGGESTIONS = [
  { icon: '🔍', text: 'Summarize the key findings from the uploaded documents', color: '#6c63ff' },
  { icon: '📊', text: 'What are the main trends identified in the data?', color: '#00d4aa' },
  { icon: '⚡', text: 'Compare and contrast the different sections of the report', color: '#ffb347' },
  { icon: '🧠', text: 'What are the most important conclusions I should know?', color: '#4facfe' },
];

/* ─── Loading Skeleton ─────────────────────────────────────────────────────── */
function MessageSkeleton() {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start', animation: 'fadeIn 0.3s ease' }}>
      <div style={{ width: 32, height: 32, borderRadius: 8, background: 'var(--surface-3)', flexShrink: 0 }} className="shimmer-bg" />
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ height: 14, borderRadius: 4, background: 'var(--surface-3)', width: '70%' }} className="shimmer-bg" />
        <div style={{ height: 14, borderRadius: 4, background: 'var(--surface-3)', width: '90%' }} className="shimmer-bg" />
        <div style={{ height: 14, borderRadius: 4, background: 'var(--surface-3)', width: '55%' }} className="shimmer-bg" />
      </div>
    </div>
  );
}

/* ─── User Message ─────────────────────────────────────────────────────────── */
function UserMessage({ message }) {
  return (
    <div style={{
      display: 'flex',
      justifyContent: 'flex-end',
      gap: 10,
      animation: 'slideUp 0.3s ease forwards',
    }}>
      <div style={{
        maxWidth: '75%',
        background: 'linear-gradient(135deg, #6c63ff, #8b85ff)',
        borderRadius: '16px 16px 4px 16px',
        padding: '12px 16px',
        boxShadow: '0 4px 20px rgba(108,99,255,0.25)',
      }}>
        <p style={{ margin: 0, color: '#fff', fontSize: '14px', lineHeight: 1.6 }}>
          {message.content}
        </p>
        <div style={{ fontSize: '11px', color: 'rgba(255,255,255,0.5)', marginTop: 6, textAlign: 'right' }}>
          {new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
        </div>
      </div>
      <div style={{
        width: 32, height: 32, borderRadius: 8, flexShrink: 0,
        background: 'linear-gradient(135deg, #6c63ff, #a18bff)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '14px',
      }}>👤</div>
    </div>
  );
}

/* ─── Assistant Message ─────────────────────────────────────────────────────── */
function AssistantMessage({ message, isStreaming, onCitationClick }) {
  const meta = message.metadata || {};
  const hasCitations = meta.citations?.length > 0;
  const hallucinationScore = meta.hallucination_score ?? 0;
  const showWarning = hallucinationScore > 0.6;

  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start', animation: 'slideUp 0.3s ease forwards' }}>
      {/* Avatar */}
      <div style={{
        width: 32, height: 32, borderRadius: 8, flexShrink: 0,
        background: 'linear-gradient(135deg, #00d4aa33, #4facfe33)',
        border: '1px solid rgba(0,212,170,0.3)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '16px',
      }}>💡</div>

      <div style={{ flex: 1, maxWidth: 'calc(100% - 44px)', minWidth: 0 }}>
        {/* Glass card */}
        <div style={{
          background: 'rgba(26,26,36,0.7)',
          backdropFilter: 'blur(20px)',
          border: '1px solid var(--border)',
          borderRadius: '4px 16px 16px 16px',
          padding: '14px 18px',
          boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
        }}>
          <div className={`prose ${isStreaming ? 'typing-cursor' : ''}`}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content || ''}
            </ReactMarkdown>
          </div>
        </div>

        {/* Meta badges */}
        {!isStreaming && (
          <div style={{ display: 'flex', gap: 6, marginTop: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            {meta.model_used && (
              <span className="badge badge-primary">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="3"/><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83"/>
                </svg>
                {meta.model_used}
              </span>
            )}
            {meta.duration_ms && (
              <span className="badge">
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
                </svg>
                {(meta.duration_ms / 1000).toFixed(1)}s
              </span>
            )}
            {showWarning && (
              <span className="badge badge-warning">
                ⚠️ Low confidence ({Math.round(hallucinationScore * 100)}%)
              </span>
            )}
            {hasCitations && (
              <button
                onClick={() => onCitationClick(meta.citations)}
                style={{
                  background: 'rgba(108,99,255,0.08)',
                  border: '1px solid rgba(108,99,255,0.25)',
                  borderRadius: 9999,
                  color: '#8b85ff',
                  fontSize: '11px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  padding: '2px 8px',
                  display: 'flex', alignItems: 'center', gap: 4,
                  transition: 'all 0.15s',
                }}
                onMouseEnter={e => { e.currentTarget.style.background = 'rgba(108,99,255,0.15)'; }}
                onMouseLeave={e => { e.currentTarget.style.background = 'rgba(108,99,255,0.08)'; }}
              >
                <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                  <polyline points="14 2 14 8 20 8"/>
                </svg>
                {meta.citations.length} source{meta.citations.length !== 1 ? 's' : ''}
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/* ─── Empty State ─────────────────────────────────────────────────────────── */
function EmptyState({ onSuggestion }) {
  return (
    <div style={{
      flex: 1, display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      padding: '40px 24px', gap: 32,
      animation: 'fadeIn 0.4s ease forwards',
    }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{
          width: 72, height: 72, borderRadius: 20,
          background: 'linear-gradient(135deg, rgba(108,99,255,0.2), rgba(0,212,170,0.15))',
          border: '1px solid rgba(108,99,255,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 20px',
          fontSize: '32px',
          boxShadow: '0 8px 32px rgba(108,99,255,0.15)',
          animation: 'float 3s ease-in-out infinite',
        }}>💡</div>
        <h2 style={{ fontSize: '22px', fontWeight: 700, marginBottom: 8 }}>
          <span className="gradient-text">What would you like to know?</span>
        </h2>
        <p style={{ color: 'var(--text-muted)', fontSize: '14px', maxWidth: 360, lineHeight: 1.6 }}>
          Ask anything about your documents. I'll find relevant information and provide accurate answers.
        </p>
      </div>

      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, width: '100%', maxWidth: 580,
      }}>
        {SUGGESTIONS.map((s, i) => (
          <button
            key={i}
            onClick={() => onSuggestion(s.text)}
            style={{
              background: 'rgba(26,26,36,0.8)',
              border: '1px solid var(--border)',
              borderRadius: 12,
              padding: '14px 16px',
              textAlign: 'left',
              cursor: 'pointer',
              color: 'var(--text)',
              transition: 'all 0.2s',
              display: 'flex', flexDirection: 'column', gap: 6,
            }}
            onMouseEnter={e => {
              e.currentTarget.style.borderColor = s.color + '66';
              e.currentTarget.style.background = s.color + '0d';
              e.currentTarget.style.transform = 'translateY(-2px)';
              e.currentTarget.style.boxShadow = `0 8px 24px ${s.color}1a`;
            }}
            onMouseLeave={e => {
              e.currentTarget.style.borderColor = 'var(--border)';
              e.currentTarget.style.background = 'rgba(26,26,36,0.8)';
              e.currentTarget.style.transform = 'translateY(0)';
              e.currentTarget.style.boxShadow = 'none';
            }}
          >
            <span style={{ fontSize: '20px' }}>{s.icon}</span>
            <span style={{ fontSize: '13px', lineHeight: 1.4, color: 'var(--text-muted)' }}>{s.text}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

/* ─── Main ChatInterface ───────────────────────────────────────────────────── */
export default function ChatInterface() {
  const { showToast } = useToast();
  const {
    sessions, currentSession, messages,
    loading: sessionLoading,
    createSession, selectSession, deleteSession, addMessage, updateLastMessage,
  } = useSession();

  const { isStreaming, fullText, metadata, error: streamError, startStream, cancelStream } = useStream();

  const [inputValue, setInputValue] = useState('');
  const [activeCitations, setActiveCitations] = useState(null);
  const [streamingMessageAdded, setStreamingMessageAdded] = useState(false);

  const textareaRef = useRef(null);
  const messagesEndRef = useRef(null);

  /* ── Auto-scroll ───────────────────────────────────────────────────────── */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, fullText]);

  /* ── Update streaming message ──────────────────────────────────────────── */
  useEffect(() => {
    if (isStreaming && streamingMessageAdded && fullText) {
      updateLastMessage(fullText);
    }
  }, [fullText, isStreaming, streamingMessageAdded, updateLastMessage]);

  /* ── Stream completion ─────────────────────────────────────────────────── */
  useEffect(() => {
    if (!isStreaming && streamingMessageAdded && metadata !== null) {
      updateLastMessage(fullText, metadata);
      setStreamingMessageAdded(false);
    }
  }, [isStreaming, metadata, streamingMessageAdded, fullText, updateLastMessage]);

  /* ── Stream error ──────────────────────────────────────────────────────── */
  useEffect(() => {
    if (streamError) {
      showToast(streamError.message || 'Streaming failed', 'error');
    }
  }, [streamError, showToast]);

  /* ── Auto-resize textarea ─────────────────────────────────────────────── */
  const handleInput = (e) => {
    const el = e.target;
    el.style.height = 'auto';
    el.style.height = Math.min(el.scrollHeight, 160) + 'px';
    setInputValue(el.value);
  };

  /* ── Keyboard shortcut ─────────────────────────────────────────────────── */
  useEffect(() => {
    const handler = (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === '/') {
        e.preventDefault();
        textareaRef.current?.focus();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  /* ── Send message ──────────────────────────────────────────────────────── */
  const handleSend = useCallback(async (text = null) => {
    const queryText = (text || inputValue).trim();
    if (!queryText || isStreaming) return;

    setInputValue('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.value = '';
    }

    // Add user message
    addMessage('user', queryText);

    // Add placeholder assistant message
    addMessage('assistant', '', {});
    setStreamingMessageAdded(true);

    // Start streaming
    startStream(queryText, currentSession?.id);
  }, [inputValue, isStreaming, addMessage, startStream, currentSession]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestion = (text) => {
    setInputValue(text);
    if (textareaRef.current) textareaRef.current.value = text;
    setTimeout(() => handleSend(text), 0);
  };

  const hasMessages = messages.length > 0;

  return (
    <div style={{ display: 'flex', height: '100%', overflow: 'hidden' }}>
      {/* Left Sidebar */}
      <SessionSidebar
        sessions={sessions}
        currentSession={currentSession}
        onSelect={selectSession}
        onDelete={deleteSession}
        onCreate={createSession}
        loading={sessionLoading}
      />

      {/* Main Chat Area */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden', background: 'var(--bg)' }}>
        {/* Top Bar */}
        <div style={{
          padding: '14px 24px',
          borderBottom: '1px solid var(--border)',
          background: 'rgba(10,10,15,0.8)',
          backdropFilter: 'blur(20px)',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <div>
            <h2 style={{ fontSize: '15px', fontWeight: 600, margin: 0 }}>
              {currentSession?.title || 'New Chat'}
            </h2>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0 }}>
              {messages.filter(m => m.role === 'user').length} message{messages.filter(m => m.role === 'user').length !== 1 ? 's' : ''}
            </p>
          </div>
          {isStreaming && (
            <button
              onClick={cancelStream}
              style={{
                background: 'rgba(255,87,87,0.1)', border: '1px solid rgba(255,87,87,0.3)',
                borderRadius: 8, color: 'var(--error)', cursor: 'pointer',
                padding: '6px 14px', fontSize: '13px', fontWeight: 500,
                display: 'flex', alignItems: 'center', gap: 6,
                animation: 'fadeIn 0.2s ease',
              }}
            >
              <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="6" width="12" height="12" rx="1"/>
              </svg>
              Stop
            </button>
          )}
        </div>

        {/* Messages */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '24px', display: 'flex', flexDirection: 'column', gap: 20 }}>
          {!hasMessages ? (
            <EmptyState onSuggestion={handleSuggestion} />
          ) : (
            <>
              {messages.map((msg) => {
                const isLastAssistant = msg.role === 'assistant' && msg === messages[messages.length - 1] && isStreaming;
                if (msg.role === 'user') {
                  return <UserMessage key={msg.id} message={msg} />;
                }
                if (msg.role === 'assistant' && !msg.content && isLastAssistant) {
                  return <MessageSkeleton key={msg.id} />;
                }
                return (
                  <AssistantMessage
                    key={msg.id}
                    message={msg}
                    isStreaming={isLastAssistant}
                    onCitationClick={(citations) => setActiveCitations(citations)}
                  />
                );
              })}
              <div ref={messagesEndRef} />
            </>
          )}
        </div>

        {/* Input Area */}
        <div style={{
          padding: '16px 24px 20px',
          borderTop: '1px solid var(--border)',
          background: 'rgba(10,10,15,0.9)',
          backdropFilter: 'blur(20px)',
          flexShrink: 0,
        }}>
          <div style={{
            display: 'flex',
            gap: 10,
            background: 'var(--surface-2)',
            border: '1px solid var(--border)',
            borderRadius: 14,
            padding: '10px 12px',
            transition: 'border-color 0.2s, box-shadow 0.2s',
          }}
            onFocusCapture={e => {
              const el = e.currentTarget;
              el.style.borderColor = 'var(--primary)';
              el.style.boxShadow = '0 0 0 3px rgba(108,99,255,0.15), 0 0 30px rgba(108,99,255,0.08)';
              el.style.animation = 'borderGlow 2s ease-in-out infinite';
            }}
            onBlurCapture={e => {
              const el = e.currentTarget;
              el.style.borderColor = 'var(--border)';
              el.style.boxShadow = 'none';
              el.style.animation = 'none';
            }}
          >
            <textarea
              ref={textareaRef}
              id="chat-input"
              value={inputValue}
              onInput={handleInput}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything about your documents… (⌃/ to focus)"
              rows={1}
              disabled={isStreaming}
              style={{
                flex: 1,
                background: 'transparent',
                border: 'none',
                outline: 'none',
                color: 'var(--text)',
                fontSize: '14px',
                lineHeight: 1.6,
                resize: 'none',
                minHeight: 24,
                maxHeight: 160,
                overflowY: 'auto',
                paddingTop: 2,
              }}
            />
            <button
              onClick={() => handleSend()}
              disabled={!inputValue.trim() || isStreaming}
              style={{
                width: 36, height: 36, borderRadius: 9,
                background: !inputValue.trim() || isStreaming ? 'var(--surface-3)' : 'linear-gradient(135deg, #6c63ff, #8b85ff)',
                border: 'none', cursor: (!inputValue.trim() || isStreaming) ? 'not-allowed' : 'pointer',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                flexShrink: 0,
                transition: 'all 0.2s',
                boxShadow: (!inputValue.trim() || isStreaming) ? 'none' : '0 4px 12px rgba(108,99,255,0.35)',
              }}
            >
              {isStreaming ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" className="animate-spin" style={{ opacity: 0.7 }}>
                  <line x1="12" y1="2" x2="12" y2="6"/><line x1="12" y1="18" x2="12" y2="22"/>
                  <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"/><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"/>
                  <line x1="2" y1="12" x2="6" y2="12"/><line x1="18" y1="12" x2="22" y2="12"/>
                </svg>
              ) : (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={!inputValue.trim() ? '#55556a' : 'white'} strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13"/><polygon points="22 2 15 22 11 13 2 9 22 2"/>
                </svg>
              )}
            </button>
          </div>
          <p style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: 8, textAlign: 'center' }}>
            Enter to send · Shift+Enter for new line · Ctrl+/ to focus
          </p>
        </div>
      </div>

      {/* Right Citations Panel */}
      {activeCitations && (
        <SourceCitations
          citations={activeCitations}
          onClose={() => setActiveCitations(null)}
        />
      )}
    </div>
  );
}
