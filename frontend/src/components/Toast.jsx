import React, { createContext, useContext, useState, useCallback } from 'react';

const ToastContext = createContext(null);

let toastId = 0;

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const showToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = ++toastId;
    setToasts((prev) => [...prev, { id, message, type }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, duration);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      <ToastStack toasts={toasts} onRemove={removeToast} />
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used within ToastProvider');
  return ctx;
}

/* ─── Icons ─────────────────────────────────────────────────────────────────── */
const icons = {
  success: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M20 6L9 17l-5-5"/>
    </svg>
  ),
  error: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
  ),
  warning: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
      <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
    </svg>
  ),
  info: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10"/>
      <line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
    </svg>
  ),
};

const typeColors = {
  success: { bg: 'rgba(0,212,170,0.1)', border: 'rgba(0,212,170,0.3)', icon: '#00d4aa' },
  error:   { bg: 'rgba(255,87,87,0.1)',  border: 'rgba(255,87,87,0.3)',  icon: '#ff5757' },
  warning: { bg: 'rgba(255,179,71,0.1)', border: 'rgba(255,179,71,0.3)', icon: '#ffb347' },
  info:    { bg: 'rgba(79,172,254,0.1)', border: 'rgba(79,172,254,0.3)', icon: '#4facfe' },
};

function ToastStack({ toasts, onRemove }) {
  return (
    <div style={{
      position: 'fixed',
      bottom: '24px',
      right: '24px',
      display: 'flex',
      flexDirection: 'column',
      gap: '10px',
      zIndex: 'var(--z-toast)',
      pointerEvents: 'none',
    }}>
      {toasts.map((toast) => (
        <ToastItem key={toast.id} toast={toast} onRemove={onRemove} />
      ))}
    </div>
  );
}

function ToastItem({ toast, onRemove }) {
  const colors = typeColors[toast.type] || typeColors.info;

  return (
    <div
      onClick={() => onRemove(toast.id)}
      style={{
        display: 'flex',
        alignItems: 'flex-start',
        gap: '10px',
        padding: '12px 16px',
        background: 'rgba(19,19,26,0.95)',
        border: `1px solid ${colors.border}`,
        borderLeft: `3px solid ${colors.icon}`,
        borderRadius: '10px',
        backdropFilter: 'blur(20px)',
        boxShadow: '0 8px 32px rgba(0,0,0,0.5)',
        minWidth: '280px',
        maxWidth: '380px',
        cursor: 'pointer',
        pointerEvents: 'auto',
        animation: 'slideInRight 0.3s cubic-bezier(0.4,0,0.2,1) forwards',
      }}
    >
      <span style={{ color: colors.icon, flexShrink: 0, marginTop: '1px' }}>{icons[toast.type]}</span>
      <span style={{ color: 'var(--text)', fontSize: '0.85rem', lineHeight: 1.5, flex: 1 }}>
        {toast.message}
      </span>
      <button
        onClick={(e) => { e.stopPropagation(); onRemove(toast.id); }}
        style={{
          background: 'none',
          border: 'none',
          color: 'var(--text-muted)',
          cursor: 'pointer',
          padding: '2px',
          flexShrink: 0,
          lineHeight: 1,
          fontSize: '16px',
        }}
      >×</button>
    </div>
  );
}
