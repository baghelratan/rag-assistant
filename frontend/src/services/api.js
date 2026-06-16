const BASE_URL = import.meta.env.VITE_API_URL === '' ? '' : (import.meta.env.VITE_API_URL || 'http://localhost:8000');

/* ─── Error Types ───────────────────────────────────────────────────────────── */
export class ApiError extends Error {
  constructor(message, status, data = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

export class NetworkError extends Error {
  constructor(message) {
    super(message);
    this.name = 'NetworkError';
  }
}

export class AbortError extends Error {
  constructor() {
    super('Request was aborted');
    this.name = 'AbortError';
  }
}

/* ─── Internal Helpers ──────────────────────────────────────────────────────── */
async function handleResponse(res) {
  if (!res.ok) {
    let data = null;
    try { data = await res.json(); } catch (_) {}
    const msg = data?.detail || data?.message || `HTTP ${res.status}`;
    throw new ApiError(msg, res.status, data);
  }
  const ct = res.headers.get('content-type') || '';
  if (ct.includes('application/json')) return res.json();
  return res.text();
}

async function apiFetch(path, options = {}) {
  try {
    const res = await fetch(`${BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    return handleResponse(res);
  } catch (err) {
    if (err instanceof ApiError) throw err;
    if (err.name === 'AbortError') throw new AbortError();
    throw new NetworkError(err.message || 'Network request failed');
  }
}

/* ─── SSE Streaming ─────────────────────────────────────────────────────────── */
/**
 * streamQuery — opens a POST SSE stream
 * @param {string} query
 * @param {string|null} sessionId
 * @param {number} topK
 * @param {(token:string) => void} onToken
 * @param {(metadata:object) => void} onComplete
 * @param {(err:Error) => void} onError
 * @returns {AbortController}
 */
export function streamQuery(query, sessionId, topK = 5, onToken, onComplete, onError) {
  const controller = new AbortController();
  const { signal } = controller;

  (async () => {
    try {
      const res = await fetch(`${BASE_URL}/api/v1/query/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, session_id: sessionId, top_k: topK }),
        signal,
      });

      if (!res.ok) {
        let data = null;
        try { data = await res.json(); } catch (_) {}
        throw new ApiError(data?.detail || `HTTP ${res.status}`, res.status, data);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        // Parse SSE lines
        const parts = buffer.split('\n\n');
        buffer = parts.pop(); // keep incomplete chunk

        for (const part of parts) {
          const lines = part.trim().split('\n');
          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const raw = line.slice(6).trim();
              if (!raw || raw === '[DONE]') continue;
              try {
                const payload = JSON.parse(raw);
                if (payload.done) {
                  onComplete?.(payload.metadata || {});
                } else if (payload.token) {
                  onToken?.(payload.token);
                }
              } catch (_) {}
            }
          }
        }
      }
    } catch (err) {
      if (err.name === 'AbortError' || signal.aborted) return;
      onError?.(err instanceof ApiError ? err : new NetworkError(err.message));
    }
  })();

  return controller;
}

/* ─── Non-streaming Query ────────────────────────────────────────────────────── */
/**
 * @param {string} query
 * @param {string|null} sessionId
 * @returns {Promise<{answer, citations, hallucination_score, model_used, duration_ms}>}
 */
export function query(queryText, sessionId) {
  return apiFetch('/api/v1/query', {
    method: 'POST',
    body: JSON.stringify({ query: queryText, session_id: sessionId }),
  });
}

/* ─── Document Ingestion ─────────────────────────────────────────────────────── */
/**
 * @param {File} file
 * @param {(pct:number)=>void} onProgress
 * @returns {Promise<{doc_id, filename, chunk_count, duration_ms, status}>}
 */
export function uploadDocument(file, onProgress) {
  return new Promise((resolve, reject) => {
    const formData = new FormData();
    formData.append('file', file);

    const xhr = new XMLHttpRequest();
    xhr.open('POST', `${BASE_URL}/api/v1/ingest`);

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.round((e.loaded / e.total) * 100));
      }
    });

    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText));
        } catch {
          resolve({ status: 'ok' });
        }
      } else {
        let data = null;
        try { data = JSON.parse(xhr.responseText); } catch (_) {}
        reject(new ApiError(data?.detail || `HTTP ${xhr.status}`, xhr.status, data));
      }
    });

    xhr.addEventListener('error', () => reject(new NetworkError('Upload failed')));
    xhr.addEventListener('abort', () => reject(new AbortError()));

    xhr.send(formData);
  });
}

/**
 * @param {string} directoryPath
 * @returns {Promise<any>}
 */
export function bulkIngest(directoryPath) {
  return apiFetch('/api/v1/ingest/bulk', {
    method: 'POST',
    body: JSON.stringify({ directory_path: directoryPath }),
  });
}

/* ─── Document Management ────────────────────────────────────────────────────── */
export function getDocuments() {
  return apiFetch('/api/v1/documents');
}

export function deleteDocument(docId) {
  return apiFetch(`/api/v1/documents/${docId}`, { method: 'DELETE' });
}

/* ─── Session Management ─────────────────────────────────────────────────────── */
export function createSession() {
  return apiFetch('/api/v1/sessions', { method: 'POST', body: JSON.stringify({}) });
}

export function getSessions() {
  return apiFetch('/api/v1/sessions');
}

export function getSession(id) {
  return apiFetch(`/api/v1/sessions/${id}`);
}

export function deleteSession(id) {
  return apiFetch(`/api/v1/sessions/${id}`, { method: 'DELETE' });
}

/* ─── System ─────────────────────────────────────────────────────────────────── */
export function getHealth() {
  return apiFetch('/api/v1/health');
}

export function getStats() {
  return apiFetch('/api/v1/stats');
}

export default {
  streamQuery,
  query,
  uploadDocument,
  bulkIngest,
  getDocuments,
  deleteDocument,
  createSession,
  getSessions,
  getSession,
  deleteSession,
  getHealth,
  getStats,
};
