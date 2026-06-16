import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink, useLocation } from 'react-router-dom';
import ChatInterface from './components/ChatInterface';
import DocumentUpload from './components/DocumentUpload';
import MonitoringDashboard from './components/MonitoringDashboard';
import { ToastProvider } from './components/Toast';
import { getHealth } from './services/api';
import './index.css';

/* ─── Nav Items ─────────────────────────────────────────────────────────────── */
const NAV_ITEMS = [
  {
    to: '/',
    exact: true,
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
      </svg>
    ),
    label: 'Chat',
  },
  {
    to: '/documents',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
        <polyline points="14 2 14 8 20 8"/>
        <line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>
        <polyline points="10 9 9 9 8 9"/>
      </svg>
    ),
    label: 'Documents',
  },
  {
    to: '/monitoring',
    icon: (
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
      </svg>
    ),
    label: 'Monitoring',
  },
];

/* ─── Left Nav Rail ──────────────────────────────────────────────────────────── */
function NavRail({ connectionStatus }) {
  const location = useLocation();

  return (
    <nav style={{
      width: 64,
      height: '100vh',
      background: 'var(--surface)',
      borderRight: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      padding: '16px 0',
      gap: 0,
      flexShrink: 0,
      zIndex: 10,
    }}>
      {/* Logo */}
      <div style={{
        width: 40, height: 40, borderRadius: 11,
        background: 'linear-gradient(135deg, #6c63ff, #a18bff)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        marginBottom: 24, flexShrink: 0,
        boxShadow: '0 4px 16px rgba(108,99,255,0.3)',
      }}>
        <span style={{ fontSize: '18px' }}>💡</span>
      </div>

      {/* Nav Links */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 4, width: '100%', padding: '0 8px' }}>
        {NAV_ITEMS.map(({ to, icon, label, exact }) => {
          const isActive = exact ? location.pathname === to : location.pathname.startsWith(to);
          return (
            <NavLink
              key={to}
              to={to}
              data-tooltip={label}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                width: '100%', padding: '10px', borderRadius: 10,
                color: isActive ? '#8b85ff' : 'var(--text-dim)',
                background: isActive ? 'rgba(108,99,255,0.12)' : 'transparent',
                border: `1px solid ${isActive ? 'rgba(108,99,255,0.25)' : 'transparent'}`,
                transition: 'all 0.15s',
                textDecoration: 'none',
              }}
              onMouseEnter={e => {
                if (!isActive) {
                  e.currentTarget.style.background = 'var(--surface-2)';
                  e.currentTarget.style.color = 'var(--text-muted)';
                }
              }}
              onMouseLeave={e => {
                if (!isActive) {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = 'var(--text-dim)';
                }
              }}
            >
              {icon}
            </NavLink>
          );
        })}
      </div>

      {/* Spacer */}
      <div style={{ flex: 1 }} />

      {/* Connection status dot */}
      <div
        data-tooltip={connectionStatus === 'online' ? 'Backend connected' : 'Backend offline'}
        style={{ marginBottom: 8 }}
      >
        <div style={{
          width: 10, height: 10, borderRadius: '50%',
          background: connectionStatus === 'online' ? 'var(--success)' : connectionStatus === 'checking' ? 'var(--warning)' : 'var(--error)',
          boxShadow: connectionStatus === 'online' ? '0 0 8px var(--success)' : 'none',
          animation: connectionStatus === 'online' ? 'pulse 2s ease infinite' : 'none',
        }} />
      </div>
    </nav>
  );
}

/* ─── App Shell ──────────────────────────────────────────────────────────────── */
function AppShell() {
  const [connectionStatus, setConnectionStatus] = useState('checking');

  useEffect(() => {
    getHealth()
      .then(() => setConnectionStatus('online'))
      .catch(() => setConnectionStatus('offline'));

    const interval = setInterval(() => {
      getHealth()
        .then(() => setConnectionStatus('online'))
        .catch(() => setConnectionStatus('offline'));
    }, 30000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
      <NavRail connectionStatus={connectionStatus} />
      <main style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
        {connectionStatus === 'offline' && (
          <div style={{
            padding: '8px 16px',
            background: 'rgba(255,87,87,0.08)',
            borderBottom: '1px solid rgba(255,87,87,0.2)',
            color: '#ff5757',
            fontSize: '12px',
            display: 'flex', alignItems: 'center', gap: 6,
            flexShrink: 0,
          }}>
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/>
              <line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/>
            </svg>
            Backend is offline — Start the server at http://localhost:8000 to enable AI features
          </div>
        )}
        <div style={{ flex: 1, overflow: 'hidden' }}>
          <Routes>
            <Route path="/" element={<ChatInterface />} />
            <Route path="/documents" element={<DocumentUpload />} />
            <Route path="/monitoring" element={<MonitoringDashboard />} />
          </Routes>
        </div>
      </main>
    </div>
  );
}

/* ─── Root App ────────────────────────────────────────────────────────────────── */
export default function App() {
  return (
    <Router>
      <ToastProvider>
        <AppShell />
      </ToastProvider>
    </Router>
  );
}
