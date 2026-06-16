import React, { useState, useRef, useCallback, useEffect } from 'react';
import { uploadDocument, getDocuments, deleteDocument, bulkIngest } from '../services/api';
import { useToast } from './Toast';

const ACCEPTED = ['application/pdf', 'text/html', 'text/csv', 'application/csv'];
const ACCEPTED_EXT = ['pdf', 'html', 'htm', 'csv'];

function getFileExt(name = '') {
  return name.split('.').pop()?.toLowerCase() || '';
}

const EXT_STYLE = {
  pdf:  { color: '#ff5757', bg: 'rgba(255,87,87,0.12)', border: 'rgba(255,87,87,0.3)', label: 'PDF' },
  html: { color: '#4facfe', bg: 'rgba(79,172,254,0.12)', border: 'rgba(79,172,254,0.3)', label: 'HTML' },
  htm:  { color: '#4facfe', bg: 'rgba(79,172,254,0.12)', border: 'rgba(79,172,254,0.3)', label: 'HTML' },
  csv:  { color: '#00d4aa', bg: 'rgba(0,212,170,0.12)', border: 'rgba(0,212,170,0.3)', label: 'CSV' },
};

function FileTypeBadge({ filename }) {
  const ext = getFileExt(filename);
  const style = EXT_STYLE[ext] || { color: '#8888a0', bg: 'rgba(136,136,160,0.12)', border: 'rgba(136,136,160,0.3)', label: ext?.toUpperCase() || 'FILE' };
  return (
    <span style={{
      background: style.bg, color: style.color,
      border: `1px solid ${style.border}`,
      borderRadius: 6, padding: '2px 7px', fontSize: '11px', fontWeight: 700,
    }}>
      {style.label}
    </span>
  );
}

function formatBytes(b = 0) {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

/* ─── Upload Queue Item ─────────────────────────────────────────────────────── */
function UploadQueueItem({ item, onRemove }) {
  const ext = getFileExt(item.file.name);
  const style = EXT_STYLE[ext] || {};

  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 10,
      padding: '12px 14px',
      display: 'flex', gap: 12, alignItems: 'center',
      animation: 'slideUp 0.25s ease forwards',
    }}>
      <div style={{
        width: 36, height: 36, borderRadius: 8, flexShrink: 0,
        background: style.bg || 'rgba(136,136,160,0.12)',
        border: `1px solid ${style.border || 'transparent'}`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <span style={{ color: style.color || '#8888a0', fontSize: '11px', fontWeight: 700 }}>{style.label || 'FILE'}</span>
      </div>

      <div style={{ flex: 1, overflow: 'hidden' }}>
        <div style={{ fontSize: '13px', fontWeight: 500, color: 'var(--text)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {item.file.name}
        </div>
        <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: 2 }}>
          {formatBytes(item.file.size)}
          {item.status === 'uploading' && ` · ${item.progress}%`}
          {item.status === 'done' && ' · ✓ Uploaded'}
          {item.status === 'error' && ` · ✗ ${item.error || 'Failed'}`}
        </div>

        {item.status === 'uploading' && (
          <div style={{ marginTop: 6, height: 3, background: 'var(--surface-3)', borderRadius: 9999, overflow: 'hidden' }}>
            <div style={{
              height: '100%', width: `${item.progress}%`,
              background: 'linear-gradient(90deg, #6c63ff, #8b85ff)',
              borderRadius: 9999, transition: 'width 0.3s ease',
            }} />
          </div>
        )}
      </div>

      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
        {item.status === 'done' && (
          <span style={{ color: 'var(--success)', fontSize: '16px' }}>✓</span>
        )}
        {item.status === 'error' && (
          <span style={{ color: 'var(--error)', fontSize: '16px' }}>✗</span>
        )}
        {item.status !== 'uploading' && (
          <button
            onClick={() => onRemove(item.id)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-dim)', padding: 4 }}
          >×</button>
        )}
      </div>
    </div>
  );
}

/* ─── Stats Card ─────────────────────────────────────────────────────────────── */
function StatsCard({ icon, label, value, color = '#6c63ff' }) {
  return (
    <div style={{
      background: 'var(--surface)',
      border: '1px solid var(--border)',
      borderRadius: 14,
      padding: '20px',
      display: 'flex', gap: 14, alignItems: 'center',
    }}>
      <div style={{
        width: 44, height: 44, borderRadius: 12, flexShrink: 0,
        background: `${color}1a`,
        border: `1px solid ${color}33`,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '20px',
      }}>{icon}</div>
      <div>
        <div style={{ fontSize: '22px', fontWeight: 700, color: 'var(--text)', lineHeight: 1 }}>{value}</div>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: 3 }}>{label}</div>
      </div>
    </div>
  );
}

/* ─── Document Table Row ─────────────────────────────────────────────────────── */
function DocRow({ doc, onDelete }) {
  const [confirm, setConfirm] = useState(false);
  return (
    <tr style={{ borderBottom: '1px solid var(--border)', transition: 'background 0.15s' }}
      onMouseEnter={e => e.currentTarget.style.background = 'rgba(255,255,255,0.02)'}
      onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
    >
      <td style={{ padding: '12px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <FileTypeBadge filename={doc.filename || ''} />
          <span style={{ fontSize: '13px', color: 'var(--text)', maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {doc.filename || doc.doc_id || '—'}
          </span>
        </div>
      </td>
      <td style={{ padding: '12px 16px', fontSize: '13px', color: 'var(--text-muted)' }}>
        {doc.chunk_count ?? '—'}
      </td>
      <td style={{ padding: '12px 16px', fontSize: '12px', color: 'var(--text-muted)' }}>
        {formatDate(doc.ingested_at || doc.created_at)}
      </td>
      <td style={{ padding: '12px 16px' }}>
        <span style={{
          background: 'rgba(0,212,170,0.1)', color: 'var(--success)',
          border: '1px solid rgba(0,212,170,0.3)',
          borderRadius: 9999, padding: '2px 8px', fontSize: '11px', fontWeight: 500,
        }}>
          {doc.status || 'ready'}
        </span>
      </td>
      <td style={{ padding: '12px 16px' }}>
        {confirm ? (
          <div style={{ display: 'flex', gap: 6 }}>
            <button
              onClick={() => { onDelete(doc.doc_id); setConfirm(false); }}
              style={{
                background: 'rgba(255,87,87,0.15)', color: 'var(--error)',
                border: '1px solid rgba(255,87,87,0.3)',
                borderRadius: 6, padding: '3px 8px', fontSize: '12px', cursor: 'pointer',
              }}
            >Confirm</button>
            <button
              onClick={() => setConfirm(false)}
              style={{
                background: 'transparent', color: 'var(--text-muted)',
                border: '1px solid var(--border)',
                borderRadius: 6, padding: '3px 8px', fontSize: '12px', cursor: 'pointer',
              }}
            >Cancel</button>
          </div>
        ) : (
          <button
            onClick={() => setConfirm(true)}
            style={{
              background: 'none', border: '1px solid rgba(255,87,87,0.2)',
              borderRadius: 6, padding: '4px 8px', cursor: 'pointer',
              color: 'var(--error)', fontSize: '12px', display: 'flex', alignItems: 'center', gap: 4,
              transition: 'all 0.15s',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = 'rgba(255,87,87,0.1)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = 'none'; }}
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/>
            </svg>
            Delete
          </button>
        )}
      </td>
    </tr>
  );
}

/* ─── Main DocumentUpload ──────────────────────────────────────────────────── */
export default function DocumentUpload() {
  const { showToast } = useToast();
  const [isDragOver, setIsDragOver] = useState(false);
  const [uploadQueue, setUploadQueue] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [docsLoading, setDocsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [sortBy, setSortBy] = useState('date');
  const [bulkPath, setBulkPath] = useState('');
  const [bulkLoading, setBulkLoading] = useState(false);
  const fileInputRef = useRef(null);

  /* ── Load documents ──────────────────────────────────────────────────── */
  const loadDocuments = useCallback(async () => {
    setDocsLoading(true);
    try {
      const data = await getDocuments();
      const docs = Array.isArray(data) ? data : (data?.documents || []);
      setDocuments(docs);
    } catch (err) {
      // Silently fail — backend may not be running
    } finally {
      setDocsLoading(false);
    }
  }, []);

  useEffect(() => { loadDocuments(); }, [loadDocuments]);

  /* ── Upload file ─────────────────────────────────────────────────────── */
  const uploadFile = useCallback(async (file) => {
    const ext = getFileExt(file.name);
    if (!ACCEPTED_EXT.includes(ext)) {
      showToast(`File type .${ext} not supported. Use PDF, HTML, or CSV.`, 'error');
      return;
    }

    const id = `upload-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    setUploadQueue((prev) => [...prev, { id, file, status: 'uploading', progress: 0 }]);

    try {
      const result = await uploadDocument(file, (pct) => {
        setUploadQueue((prev) => prev.map((q) => q.id === id ? { ...q, progress: pct } : q));
      });
      setUploadQueue((prev) => prev.map((q) => q.id === id ? { ...q, status: 'done', progress: 100 } : q));
      showToast(`✓ ${file.name} uploaded (${result.chunk_count ?? '?'} chunks)`, 'success');
      loadDocuments();
    } catch (err) {
      setUploadQueue((prev) => prev.map((q) => q.id === id ? { ...q, status: 'error', error: err.message } : q));
      showToast(`Failed to upload ${file.name}: ${err.message}`, 'error');
    }
  }, [showToast, loadDocuments]);

  /* ── Drop handler ────────────────────────────────────────────────────── */
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragOver(false);
    const files = Array.from(e.dataTransfer.files);
    files.forEach(uploadFile);
  };

  /* ── File input ──────────────────────────────────────────────────────── */
  const handleFileChange = (e) => {
    const files = Array.from(e.target.files || []);
    files.forEach(uploadFile);
    e.target.value = '';
  };

  /* ── Delete document ─────────────────────────────────────────────────── */
  const handleDelete = useCallback(async (docId) => {
    try {
      await deleteDocument(docId);
      setDocuments((prev) => prev.filter((d) => d.doc_id !== docId));
      showToast('Document deleted', 'success');
    } catch (err) {
      showToast(`Delete failed: ${err.message}`, 'error');
    }
  }, [showToast]);

  /* ── Bulk ingest ─────────────────────────────────────────────────────── */
  const handleBulkIngest = async () => {
    if (!bulkPath.trim()) return;
    setBulkLoading(true);
    try {
      const result = await bulkIngest(bulkPath.trim());
      showToast(`Bulk ingest started successfully`, 'success');
      setBulkPath('');
      setTimeout(loadDocuments, 2000);
    } catch (err) {
      showToast(`Bulk ingest failed: ${err.message}`, 'error');
    } finally {
      setBulkLoading(false);
    }
  };

  /* ── Filter & sort ───────────────────────────────────────────────────── */
  const filtered = documents
    .filter((d) => !search || (d.filename || '').toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (sortBy === 'name') return (a.filename || '').localeCompare(b.filename || '');
      if (sortBy === 'chunks') return (b.chunk_count || 0) - (a.chunk_count || 0);
      return new Date(b.ingested_at || b.created_at || 0) - new Date(a.ingested_at || a.created_at || 0);
    });

  const totalChunks = documents.reduce((s, d) => s + (d.chunk_count || 0), 0);

  return (
    <div style={{ height: '100%', overflowY: 'auto', padding: '28px 32px', background: 'var(--bg)' }}>
      <div style={{ maxWidth: 1000, margin: '0 auto' }}>
        {/* Header */}
        <div style={{ marginBottom: 28 }}>
          <h1 style={{ fontSize: '22px', fontWeight: 700, marginBottom: 6 }}>
            <span className="gradient-text">Document Management</span>
          </h1>
          <p style={{ color: 'var(--text-muted)', fontSize: '14px' }}>
            Upload and manage documents for AI-powered retrieval. Supports PDF, HTML, and CSV.
          </p>
        </div>

        {/* Stats */}
        <div className="grid-3" style={{ marginBottom: 28 }}>
          <StatsCard icon="📄" label="Total Documents" value={documents.length} color="#6c63ff" />
          <StatsCard icon="🧩" label="Total Chunks" value={totalChunks.toLocaleString()} color="#00d4aa" />
          <StatsCard icon="⚡" label="Upload Queue" value={uploadQueue.filter(q => q.status === 'uploading').length} color="#ffb347" />
        </div>

        {/* Drop Zone */}
        <div
          onDragEnter={() => setIsDragOver(true)}
          onDragLeave={() => setIsDragOver(false)}
          onDragOver={(e) => e.preventDefault()}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current?.click()}
          style={{
            border: `2px dashed ${isDragOver ? 'var(--primary)' : 'var(--border-2)'}`,
            borderRadius: 16,
            padding: '40px 24px',
            textAlign: 'center',
            cursor: 'pointer',
            background: isDragOver ? 'rgba(108,99,255,0.06)' : 'var(--surface)',
            transition: 'all 0.2s',
            marginBottom: 20,
            boxShadow: isDragOver ? '0 0 0 4px rgba(108,99,255,0.1)' : 'none',
          }}
        >
          <input ref={fileInputRef} type="file" multiple accept=".pdf,.html,.htm,.csv" onChange={handleFileChange} style={{ display: 'none' }} />
          <div style={{ fontSize: '40px', marginBottom: 12, animation: isDragOver ? 'float 1s ease-in-out infinite' : 'none' }}>📤</div>
          <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: 6, color: isDragOver ? 'var(--primary-light)' : 'var(--text)' }}>
            {isDragOver ? 'Drop files to upload' : 'Drag & drop files here'}
          </h3>
          <p style={{ color: 'var(--text-muted)', fontSize: '13px', marginBottom: 14 }}>
            or click to browse your computer
          </p>
          <div style={{ display: 'flex', gap: 8, justifyContent: 'center' }}>
            {['PDF', 'HTML', 'CSV'].map((t) => {
              const s = t === 'PDF' ? EXT_STYLE.pdf : t === 'HTML' ? EXT_STYLE.html : EXT_STYLE.csv;
              return (
                <span key={t} style={{
                  background: s.bg, color: s.color, border: `1px solid ${s.border}`,
                  borderRadius: 6, padding: '3px 10px', fontSize: '12px', fontWeight: 600,
                }}>{t}</span>
              );
            })}
          </div>
        </div>

        {/* Upload Queue */}
        {uploadQueue.length > 0 && (
          <div style={{ marginBottom: 24 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <h3 style={{ fontSize: '14px', fontWeight: 600 }}>Upload Queue</h3>
              <button onClick={() => setUploadQueue(prev => prev.filter(q => q.status === 'uploading'))}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '12px' }}>
                Clear completed
              </button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {uploadQueue.map((item) => (
                <UploadQueueItem key={item.id} item={item} onRemove={(id) => setUploadQueue(prev => prev.filter(q => q.id !== id))} />
              ))}
            </div>
          </div>
        )}

        {/* Bulk Ingest */}
        <div style={{
          background: 'var(--surface)',
          border: '1px solid var(--border)',
          borderRadius: 14,
          padding: '18px 20px',
          marginBottom: 28,
        }}>
          <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: 12 }}>Bulk Directory Ingest</h3>
          <div style={{ display: 'flex', gap: 10 }}>
            <input
              type="text"
              className="input"
              value={bulkPath}
              onChange={(e) => setBulkPath(e.target.value)}
              placeholder="e.g. /data/documents or C:\documents"
              style={{ flex: 1 }}
              onKeyDown={(e) => e.key === 'Enter' && handleBulkIngest()}
            />
            <button
              onClick={handleBulkIngest}
              disabled={!bulkPath.trim() || bulkLoading}
              className="btn btn-primary"
            >
              {bulkLoading ? (
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" className="animate-spin">
                  <line x1="12" y1="2" x2="12" y2="6"/>
                </svg>
              ) : null}
              {bulkLoading ? 'Ingesting…' : 'Start Ingest'}
            </button>
          </div>
        </div>

        {/* Document Table */}
        <div style={{ background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 16, overflow: 'hidden' }}>
          {/* Table header controls */}
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border)', display: 'flex', gap: 10, alignItems: 'center' }}>
            <h3 style={{ fontSize: '14px', fontWeight: 600, flex: 1 }}>
              Ingested Documents ({filtered.length})
            </h3>
            <input
              type="text"
              className="input"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search documents…"
              style={{ width: 200, fontSize: '12px', padding: '6px 10px' }}
            />
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="input"
              style={{ width: 130, fontSize: '12px', padding: '6px 10px' }}
            >
              <option value="date">Sort: Date</option>
              <option value="name">Sort: Name</option>
              <option value="chunks">Sort: Chunks</option>
            </select>
            <button onClick={loadDocuments} className="btn btn-ghost btn-sm">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="23 4 23 10 17 10"/><polyline points="1 20 1 14 7 14"/>
                <path d="M3.51 9a9 9 0 0114.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0020.49 15"/>
              </svg>
              Refresh
            </button>
          </div>

          {/* Table */}
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: 'var(--surface-2)' }}>
                  {['Filename', 'Chunks', 'Ingested At', 'Status', 'Actions'].map((h) => (
                    <th key={h} style={{ padding: '10px 16px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {docsLoading ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={5} style={{ padding: '14px 16px' }}>
                        <div style={{ height: 14, borderRadius: 4, background: 'var(--surface-2)' }} className="shimmer-bg" />
                      </td>
                    </tr>
                  ))
                ) : filtered.length === 0 ? (
                  <tr>
                    <td colSpan={5} style={{ padding: '40px', textAlign: 'center', color: 'var(--text-muted)' }}>
                      <div style={{ fontSize: '32px', marginBottom: 8 }}>📂</div>
                      <p style={{ fontSize: '14px' }}>
                        {search ? 'No documents match your search' : 'No documents ingested yet. Upload files above.'}
                      </p>
                    </td>
                  </tr>
                ) : (
                  filtered.map((doc) => (
                    <DocRow key={doc.doc_id || doc.filename} doc={doc} onDelete={handleDelete} />
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
