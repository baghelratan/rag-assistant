import React from 'react';

function formatDate(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diff = now - d;
  if (diff < 60000) return 'just now';
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
  return d.toLocaleDateString();
}

function SessionItem({ session, isActive, onSelect, onDelete }) {
  const [hovered, setHovered] = React.useState(false);
  const [deleteHover, setDeleteHover] = React.useState(false);

  return (
    <div
      onClick={() => onSelect(session.id)}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => { setHovered(false); setDeleteHover(false); }}
      style={{
        padding: '10px 12px',
        borderRadius: 10,
        cursor: 'pointer',
        background: isActive
          ? 'rgba(108,99,255,0.12)'
          : hovered ? 'var(--surface-2)' : 'transparent',
        border: `1px solid ${isActive ? 'rgba(108,99,255,0.3)' : 'transparent'}`,
        transition: 'all 0.15s',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        position: 'relative',
      }}
    >
      {/* Session icon */}
      <div style={{
        width: 32, height: 32, borderRadius: 8,
        background: isActive ? 'rgba(108,99,255,0.2)' : 'var(--surface-3)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        flexShrink: 0, transition: 'background 0.15s',
      }}>
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
          stroke={isActive ? '#8b85ff' : 'var(--text-muted)'}
          strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
        </svg>
      </div>

      {/* Text */}
      <div style={{ flex: 1, overflow: 'hidden' }}>
        <div style={{
          fontSize: '13px', fontWeight: isActive ? 600 : 400,
          color: isActive ? 'var(--text)' : 'var(--text-muted)',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          lineHeight: 1.3,
        }}>
          {session.title || 'New Chat'}
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-dim)', marginTop: 1 }}>
          {formatDate(session.created_at)}
        </div>
      </div>

      {/* Delete button */}
      {(hovered || isActive) && (
        <button
          onClick={(e) => { e.stopPropagation(); onDelete(session.id); }}
          onMouseEnter={() => setDeleteHover(true)}
          onMouseLeave={() => setDeleteHover(false)}
          style={{
            background: deleteHover ? 'rgba(255,87,87,0.15)' : 'transparent',
            border: 'none', cursor: 'pointer',
            color: deleteHover ? 'var(--error)' : 'var(--text-dim)',
            padding: '4px', borderRadius: 5,
            display: 'flex', alignItems: 'center',
            transition: 'all 0.15s', flexShrink: 0,
          }}
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14H6L5 6"/>
            <path d="M10 11v6M14 11v6"/>
            <path d="M9 6V4h6v2"/>
          </svg>
        </button>
      )}
    </div>
  );
}

export default function SessionSidebar({ sessions, currentSession, onSelect, onDelete, onCreate, loading }) {
  return (
    <div style={{
      width: 260,
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--surface)',
      borderRight: '1px solid var(--border)',
    }}>
      {/* Header */}
      <div style={{
        padding: '20px 16px 14px',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 14 }}>
          <div style={{
            width: 32, height: 32, borderRadius: 8,
            background: 'linear-gradient(135deg, #6c63ff, #a18bff)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            flexShrink: 0,
          }}>
            <span style={{ fontSize: '16px' }}>💡</span>
          </div>
          <div>
            <div style={{ fontSize: '13px', fontWeight: 700, color: 'var(--text)', lineHeight: 1.2 }}>RAG Assistant</div>
            <div style={{ fontSize: '10px', color: 'var(--text-muted)' }}>AI-Powered Intelligence</div>
          </div>
        </div>

        <button
          onClick={onCreate}
          disabled={loading}
          style={{
            width: '100%',
            padding: '9px 14px',
            background: 'linear-gradient(135deg, #6c63ff, #8b85ff)',
            border: 'none',
            borderRadius: 10,
            color: '#fff',
            fontSize: '13px',
            fontWeight: 600,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            transition: 'all 0.2s',
            boxShadow: '0 4px 16px rgba(108,99,255,0.3)',
          }}
          onMouseEnter={e => { e.currentTarget.style.transform = 'translateY(-1px)'; e.currentTarget.style.boxShadow = '0 6px 24px rgba(108,99,255,0.45)'; }}
          onMouseLeave={e => { e.currentTarget.style.transform = 'translateY(0)'; e.currentTarget.style.boxShadow = '0 4px 16px rgba(108,99,255,0.3)'; }}
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
            <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          New Chat
        </button>
      </div>

      {/* Sessions label */}
      <div style={{ padding: '12px 16px 4px' }}>
        <span style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-dim)', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          Recent Chats
        </span>
      </div>

      {/* Session List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '4px 8px 12px' }}>
        {sessions.length === 0 ? (
          <div style={{
            textAlign: 'center', padding: '32px 16px',
            color: 'var(--text-dim)', fontSize: '12px', lineHeight: 1.6,
          }}>
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" style={{ margin: '0 auto 8px', opacity: 0.3 }}>
              <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
            </svg>
            <p>No conversations yet.<br />Start a new chat above.</p>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
            {sessions.map((s) => (
              <SessionItem
                key={s.id}
                session={s}
                isActive={currentSession?.id === s.id}
                onSelect={onSelect}
                onDelete={onDelete}
              />
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div style={{
        padding: '12px 16px',
        borderTop: '1px solid var(--border)',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <div style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
          {sessions.length} conversation{sessions.length !== 1 ? 's' : ''}
        </div>
      </div>
    </div>
  );
}
