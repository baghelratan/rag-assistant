import React, { useState, useEffect, useRef, useCallback } from 'react';
import { getHealth, getStats } from '../services/api';

/* ─── Helpers ────────────────────────────────────────────────────────────────── */
function formatUptime(ms) {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return `${h}h ${m}m ${sec}s`;
}

/* ─── Status Card ─────────────────────────────────────────────────────────────── */
function StatusCard({ name, status, description }) {
  const isOnline = status === 'healthy' || status === 'online' || status === true || status === 'ok';
  const isWarn   = status === 'degraded' || status === 'warning';
  const color = isOnline ? '#00d4aa' : isWarn ? '#ffb347' : '#ff5757';
  const label = isOnline ? 'ONLINE' : isWarn ? 'DEGRADED' : 'OFFLINE';

  return (
    <div style={{
      background: 'var(--surface)',
      border: `1px solid ${color}22`,
      borderRadius: 14,
      padding: '18px 20px',
      display: 'flex', alignItems: 'center', gap: 14,
      transition: 'all 0.2s',
    }}>
      <div style={{
        width: 44, height: 44, borderRadius: 12,
        background: `${color}15`,
        border: `1px solid ${color}33`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        position: 'relative',
      }}>
        <div style={{
          width: 12, height: 12, borderRadius: '50%',
          background: color,
          boxShadow: isOnline ? `0 0 8px ${color}` : 'none',
          animation: isOnline ? 'pulse 2s ease infinite' : 'none',
        }} />
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text)', marginBottom: 2 }}>{name}</div>
        {description && <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{description}</div>}
      </div>
      <span style={{
        background: `${color}15`, color, border: `1px solid ${color}33`,
        borderRadius: 9999, padding: '3px 10px', fontSize: '11px', fontWeight: 700,
        letterSpacing: '0.05em',
      }}>{label}</span>
    </div>
  );
}

/* ─── Metric Card ─────────────────────────────────────────────────────────────── */
function MetricCard({ icon, label, value, unit, sub, color = '#6c63ff' }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 14,
      padding: '20px',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 10 }}>
        <span style={{ fontSize: '20px' }}>{icon}</span>
        {sub && (
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', background: 'var(--surface-2)', borderRadius: 6, padding: '2px 6px' }}>
            {sub}
          </span>
        )}
      </div>
      <div style={{ fontSize: '28px', fontWeight: 700, color: 'var(--text)', lineHeight: 1, marginBottom: 4 }}>
        <span style={{ background: `linear-gradient(135deg, ${color}, ${color}aa)`, WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>
          {value}
        </span>
        {unit && <span style={{ fontSize: '14px', fontWeight: 400, color: 'var(--text-muted)', marginLeft: 4, WebkitTextFillColor: 'var(--text-muted)' }}>{unit}</span>}
      </div>
      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{label}</div>
    </div>
  );
}

/* ─── Query Log Row ──────────────────────────────────────────────────────────── */
function QueryRow({ log }) {
  const hallucinationScore = log.hallucination_score ?? 0;
  const scoreColor = hallucinationScore > 0.6 ? '#ff5757' : hallucinationScore > 0.3 ? '#ffb347' : '#00d4aa';
  return (
    <tr style={{ borderBottom: '1px solid var(--border)' }}
      onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >
      <td style={{ padding: '10px 14px', fontSize: '13px', color: 'var(--text)', maxWidth: 240, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {log.query}
      </td>
      <td style={{ padding: '10px 14px', fontSize: '12px', color: 'var(--text-muted)' }}>
        {log.latency_ms ? `${log.latency_ms}ms` : '—'}
      </td>
      <td style={{ padding: '10px 14px' }}>
        <span style={{
          background: 'rgba(108,99,255,0.1)', color: '#8b85ff',
          border: '1px solid rgba(108,99,255,0.25)',
          borderRadius: 9999, padding: '2px 7px', fontSize: '11px',
        }}>{log.model || '—'}</span>
      </td>
      <td style={{ padding: '10px 14px' }}>
        <span style={{ color: scoreColor, fontSize: '12px', fontWeight: 600 }}>
          {Math.round(hallucinationScore * 100)}%
        </span>
      </td>
      <td style={{ padding: '10px 14px', fontSize: '11px', color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>
        {log.timestamp ? new Date(log.timestamp).toLocaleTimeString() : '—'}
      </td>
    </tr>
  );
}

/* ─── Main MonitoringDashboard ──────────────────────────────────────────────── */
export default function MonitoringDashboard() {
  const [health, setHealth] = useState(null);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(null);
  const [uptimeMs, setUptimeMs] = useState(0);
  const [queryLog, setQueryLog] = useState([]);
  const mountedAt = useRef(Date.now());
  const intervalRef = useRef(null);

  /* ── Mock query log (realistic demo) ──────────────────────────────────── */
  useEffect(() => {
    const mockLog = [
      { query: 'Summarize the annual report findings', latency_ms: 840, model: 'Gemini 1.5 Flash', hallucination_score: 0.05, timestamp: new Date(Date.now() - 30000).toISOString() },
      { query: 'What are the key risk factors mentioned?', latency_ms: 1240, model: 'Gemini 1.5 Flash', hallucination_score: 0.12, timestamp: new Date(Date.now() - 90000).toISOString() },
      { query: 'Compare Q1 vs Q2 performance metrics', latency_ms: 680, model: 'GPT-4o-mini', hallucination_score: 0.08, timestamp: new Date(Date.now() - 180000).toISOString() },
      { query: 'List all recommended actions from section 3', latency_ms: 520, model: 'Gemini 1.5 Flash', hallucination_score: 0.03, timestamp: new Date(Date.now() - 300000).toISOString() },
      { query: 'What is the total revenue projection?', latency_ms: 960, model: 'GPT-4o-mini', hallucination_score: 0.65, timestamp: new Date(Date.now() - 450000).toISOString() },
    ];
    setQueryLog(mockLog);
  }, []);

  /* ── Fetch health + stats ─────────────────────────────────────────────── */
  const fetchData = useCallback(async () => {
    try {
      const [h, s] = await Promise.allSettled([getHealth(), getStats()]);
      if (h.status === 'fulfilled') setHealth(h.value);
      if (s.status === 'fulfilled') setStats(s.value);
    } catch (_) {}
    setLastRefresh(new Date());
    setLoading(false);
  }, []);

  /* ── Auto-refresh every 10s ──────────────────────────────────────────── */
  useEffect(() => {
    fetchData();
    intervalRef.current = setInterval(fetchData, 10000);
    return () => clearInterval(intervalRef.current);
  }, [fetchData]);

  /* ── Uptime counter ──────────────────────────────────────────────────── */
  useEffect(() => {
    const timer = setInterval(() => {
      setUptimeMs(Date.now() - mountedAt.current);
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  /* ── Derive service statuses ─────────────────────────────────────────── */
  const services = [
    { name: 'Vector Database', status: health?.vector_db ?? health?.vectordb ?? (health ? 'healthy' : 'offline'), description: 'Chroma / Qdrant retrieval engine' },
    { name: 'LLM API', status: health?.llm ?? health?.llm_api ?? (health ? 'healthy' : 'offline'), description: 'Gemini / OpenAI endpoint' },
    { name: 'Embedding Service', status: health?.embedder ?? health?.embedding ?? (health ? 'healthy' : 'offline'), description: 'Text→Vector transformer' },
    { name: 'Session Database', status: health?.session_db ?? health?.session ?? (health ? 'healthy' : 'offline'), description: 'Conversation history store' },
  ];

  const avgLatency = queryLog.length ? Math.round(queryLog.reduce((s, q) => s + (q.latency_ms || 0), 0) / queryLog.length) : 0;
  const p95 = queryLog.length ? Math.round([...queryLog].sort((a, b) => (b.latency_ms || 0) - (a.latency_ms || 0))[Math.floor(queryLog.length * 0.05)]?.latency_ms || 0) : 0;

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '28px 32px', background: 'var(--bg)' }}>
      <div style={{ maxWidth: 1000, margin: '0 auto' }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 28 }}>
          <div>
            <h1 style={{ fontSize: '22px', fontWeight: 700, marginBottom: 6 }}>
              <span className="gradient-text">System Monitoring</span>
            </h1>
            <p style={{ color: 'var(--text-muted)', fontSize: '14px' }}>
              Real-time health and performance metrics
            </p>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 6 }}>
            <button
              onClick={fetchData}
              className="btn btn-ghost btn-sm"
              style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
                <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
              </svg>
              Refresh
            </button>
            {lastRefresh && (
              <span style={{ fontSize: '11px', color: 'var(--text-dim)' }}>
                Updated {lastRefresh.toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>

        {/* Service Health */}
        <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 12, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          Service Health
        </h2>
        <div className="grid-2" style={{ marginBottom: 28 }}>
          {services.map((s) => (
            <StatusCard key={s.name} {...s} />
          ))}
        </div>

        {/* Stats Grid */}
        <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 12, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          System Statistics
        </h2>
        <div className="grid-4" style={{ marginBottom: 28 }}>
          <MetricCard icon="📄" label="Total Documents" value={stats?.total_documents ?? stats?.document_count ?? '—'} color="#6c63ff" />
          <MetricCard icon="🧩" label="Total Chunks" value={(stats?.total_chunks ?? stats?.chunk_count ?? 0).toLocaleString()} color="#00d4aa" />
          <MetricCard icon="💬" label="Active Sessions" value={stats?.active_sessions ?? stats?.session_count ?? '—'} color="#4facfe" />
          <MetricCard icon="⚡" label="Cache Hit Rate" value={stats?.cache_hit_rate ?? '—'} unit="%" color="#ffb347" />
        </div>

        {/* Performance Metrics */}
        <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 12, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          Performance
        </h2>
        <div className="grid-3" style={{ marginBottom: 28 }}>
          <MetricCard icon="⏱" label="Average Latency" value={avgLatency || '—'} unit="ms" sub="last 5 queries" color="#6c63ff" />
          <MetricCard icon="📈" label="P95 Latency" value={p95 || '—'} unit="ms" sub="95th percentile" color="#ffb347" />
          <MetricCard icon="⏰" label="Session Uptime" value={formatUptime(uptimeMs)} color="#00d4aa" />
        </div>

        {/* Recent Queries */}
        <h2 style={{ fontSize: '14px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 12, letterSpacing: '0.06em', textTransform: 'uppercase' }}>
          Recent Query Log
        </h2>
        <div style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 14,
          overflow: 'hidden',
        }}>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--surface-2)' }}>
                  {['Query', 'Latency', 'Model', 'Confidence', 'Time'].map(h => (
                    <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {queryLog.length === 0 ? (
                  <tr>
                    <td colSpan={5} style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '13px' }}>
                      No queries recorded yet
                    </td>
                  </tr>
                ) : (
                  queryLog.map((log, i) => <QueryRow key={i} log={log} />)
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Auto-refresh info */}
        <p style={{ fontSize: '11px', color: 'var(--text-dim)', textAlign: 'center', marginTop: 16 }}>
          Auto-refreshing every 10 seconds
        </p>
      </div>
    </div>
  );
}
