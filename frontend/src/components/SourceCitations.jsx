import React, { useState } from 'react';

/* ─── File Type Config ────────────────────────────────────────────────────────── */
const FILE_TYPES = {
  pdf:  { color: '#ff5757', bg: 'rgba(255,87,87,0.12)',   border: 'rgba(255,87,87,0.3)',   label: 'PDF' },
  html: { color: '#4facfe', bg: 'rgba(79,172,254,0.12)', border: 'rgba(79,172,254,0.3)', label: 'HTML' },
  csv:  { color: '#00d4aa', bg: 'rgba(0,212,170,0.12)',  border: 'rgba(0,212,170,0.3)',  label: 'CSV' },
};

function getFileType(name = '') {
  const ext = name.split('.').pop()?.toLowerCase();
  return FILE_TYPES[ext] || { color: '#8888a0', bg: 'rgba(136,136,160,0.12)', border: 'rgba(136,136,160,0.3)', label: ext?.toUpperCase() || 'FILE' };
}

function FileTypeIcon({ type }) {
  const cfg = FILE_TYPES[type] || { color: '#8888a0', label: '?' };
  return (
    <div style={{
      width: 32, height: 32,
      borderRadius: 6,
      background: cfg.bg || 'rgba(136,136,160,0.12)',
      border: `1px solid ${cfg.border || 'transparent'}`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexShrink: 0,
    }}>
      <span style={{ color: cfg.color, fontSize: '10px', fontWeight: 700 }}>{cfg.label}</span>
    </div>
  );
}

function RelevanceBar({ score }) {
  const pct = Math.round((score || 0) * 100);
  const color = pct >= 80 ? '#00d4aa' : pct >= 50 ? '#ffb347' : '#ff5757';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ flex: 1, height: 4, background: 'var(--surface-3)', borderRadius: 9999, overflow: 'hidden' }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          background: `linear-gradient(90deg, ${color}88, ${color})`,
          borderRadius: 9999,
          transition: 'width 0.5s ease',
        }} />
      </div>
      <span style={{ fontSize: '11px', color, fontWeight: 600, minWidth: 32 }}>{pct}%</span>
    </div>
  );
}

function CitationCard({ citation, index }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const fileType = getFileType(citation.source || '');
  const ext = (citation.source || '').split('.').pop()?.toLowerCase();
  const snippet = citation.text || citation.content || citation.snippet || '';
  const isLong = snippet.length > 200;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(snippet);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (_) {}
  };

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 12,
      overflow: 'hidden',
      transition: 'border-color 0.2s',
    }}
      onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--border-2)'}
      onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
    >
      {/* Header */}
      <div style={{
        padding: '10px 14px',
        background: 'var(--surface-2)',
        display: 'flex', alignItems: 'center', gap: 10,
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{
          width: 22, height: 22, borderRadius: 4,
          background: fileType.bg,
          border: `1px solid ${fileType.border}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
        }}>
          <span style={{ color: fileType.color, fontSize: '8px', fontWeight: 700 }}>{fileType.label}</span>
        </div>

        <div style={{ flex: 1, overflow: 'hidden' }}>
          <div style={{
            fontSize: '12px', fontWeight: 600, color: 'var(--text)',
            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          }}>
            {citation.source || 'Unknown Source'}
          </div>
          {(citation.page || citation.row) && (
            <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              {citation.page ? `Page ${citation.page}` : `Row ${citation.row}`}
            </div>
          )}
        </div>

        <span style={{
          background: 'rgba(108,99,255,0.12)',
          color: '#8b85ff',
          border: '1px solid rgba(108,99,255,0.3)',
          borderRadius: 9999,
          padding: '2px 8px',
          fontSize: '11px',
          fontWeight: 600,
          flexShrink: 0,
        }}>#{index + 1}</span>
      </div>

      {/* Relevance Score */}
      <div style={{ padding: '10px 14px 4px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 500 }}>Relevance</span>
        </div>
        <RelevanceBar score={citation.score ?? citation.relevance_score ?? 0.85} />
      </div>

      {/* Snippet */}
      {snippet && (
        <div style={{ padding: '8px 14px 12px' }}>
          <div style={{
            fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.65,
            overflow: 'hidden',
            maxHeight: expanded ? 'none' : '80px',
            position: 'relative',
          }}>
            {expanded ? snippet : snippet.slice(0, 200)}
            {!expanded && isLong && (
              <div style={{
                position: 'absolute', bottom: 0, left: 0, right: 0,
                height: 32,
                background: 'linear-gradient(transparent, var(--surface))',
              }} />
            )}
          </div>
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            {isLong && (
              <button
                onClick={() => setExpanded(!expanded)}
                style={{
                  background: 'none', border: 'none', cursor: 'pointer',
                  color: 'var(--primary-light)', fontSize: '11px', fontWeight: 500, padding: 0,
                }}
              >
                {expanded ? 'Show less ↑' : 'Show more ↓'}
              </button>
            )}
            <button
              onClick={handleCopy}
              style={{
                marginLeft: 'auto',
                background: copied ? 'rgba(0,212,170,0.1)' : 'var(--surface-2)',
                border: `1px solid ${copied ? 'rgba(0,212,170,0.3)' : 'var(--border)'}`,
                borderRadius: 6,
                color: copied ? 'var(--success)' : 'var(--text-muted)',
                fontSize: '11px', cursor: 'pointer', padding: '3px 8px',
                transition: 'all 0.2s',
              }}
            >
              {copied ? '✓ Copied' : 'Copy'}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Main Component ─────────────────────────────────────────────────────────── */
export default function SourceCitations({ citations = [], onClose }) {
  const [searchTerm, setSearchTerm] = useState('');

  const filtered = citations.filter((c) =>
    !searchTerm || (c.source || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (c.text || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleExport = () => {
    const json = JSON.stringify(citations, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `citations-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div style={{
      width: 320,
      height: '100%',
      display: 'flex',
      flexDirection: 'column',
      background: 'var(--surface)',
      borderLeft: '1px solid var(--border)',
      animation: 'slideInRight 0.25s ease forwards',
    }}>
      {/* Header */}
      <div style={{
        padding: '16px 16px 12px',
        borderBottom: '1px solid var(--border)',
        background: 'var(--surface-2)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
          <div>
            <h3 style={{ fontSize: '14px', fontWeight: 600, margin: 0 }}>Sources</h3>
            <p style={{ fontSize: '12px', color: 'var(--text-muted)', margin: 0 }}>
              {citations.length} citation{citations.length !== 1 ? 's' : ''}
            </p>
          </div>
          <div style={{ display: 'flex', gap: 6 }}>
            {citations.length > 0 && (
              <button
                onClick={handleExport}
                data-tooltip="Export JSON"
                style={{
                  background: 'var(--surface-3)', border: '1px solid var(--border)',
                  borderRadius: 6, color: 'var(--text-muted)', cursor: 'pointer',
                  padding: '5px 8px', fontSize: '11px', display: 'flex', alignItems: 'center', gap: 4,
                }}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/>
                </svg>
                Export
              </button>
            )}
            <button
              onClick={onClose}
              style={{
                background: 'none', border: 'none', cursor: 'pointer',
                color: 'var(--text-muted)', padding: '4px', borderRadius: 6,
                display: 'flex', alignItems: 'center',
              }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
              </svg>
            </button>
          </div>
        </div>

        {citations.length > 2 && (
          <input
            type="text"
            placeholder="Filter citations..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="input"
            style={{ fontSize: '12px', padding: '6px 10px' }}
          />
        )}
      </div>

      {/* Citation List */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
        {citations.length === 0 ? (
          <div style={{
            display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
            height: '100%', gap: 12, color: 'var(--text-muted)', textAlign: 'center',
          }}>
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.3">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
              <polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/>
            </svg>
            <p style={{ fontSize: '13px' }}>No citations available</p>
          </div>
        ) : filtered.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '24px', color: 'var(--text-muted)', fontSize: '13px' }}>
            No citations match your filter
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {filtered.map((c, i) => (
              <CitationCard key={c.id || i} citation={c} index={i} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
