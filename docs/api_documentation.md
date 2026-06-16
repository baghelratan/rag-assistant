# RAG Assistant — API Documentation

## Base URL

```
http://localhost:8000
```

For production: set `VITE_API_URL` to your deployed backend URL.

## Authentication

Currently, no authentication is required (rate limiting by IP). For production, add Bearer token authentication.

## Common Headers

```
Content-Type: application/json
Accept: application/json
```

---

## Endpoints

### Health & Status

#### `GET /api/v1/health`

Returns detailed health status of all system components.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 3600,
  "components": {
    "vector_db": {"status": "healthy", "doc_count": 15420},
    "llm": {"status": "healthy", "primary_model": "gemini-1.5-flash"},
    "embedder": {"status": "healthy", "model": "all-MiniLM-L6-v2"},
    "session_db": {"status": "healthy", "session_count": 42}
  }
}
```

#### `GET /api/v1/stats`

Returns system statistics.

**Response:**
```json
{
  "total_documents": 1250,
  "total_chunks": 48320,
  "index_size_mb": 245.6,
  "cache_stats": {
    "size_bytes": 10485760,
    "hit_rate": 0.34
  },
  "active_sessions": 8
}
```

#### `GET /metrics`

Returns Prometheus metrics in text format (for scraping).

---

### Document Ingestion

#### `POST /api/v1/ingest`

Upload a single document for ingestion.

**Request:** `multipart/form-data`
- `file`: File (PDF, HTML, or CSV)

**Response:**
```json
{
  "doc_id": "abc123",
  "filename": "report_2024.pdf",
  "chunk_count": 47,
  "duration_ms": 1240,
  "status": "success"
}
```

**Error Responses:**
- `400` — Unsupported file type
- `413` — File too large (max 50MB)
- `422` — Invalid form data
- `429` — Rate limit exceeded

#### `POST /api/v1/ingest/bulk`

Ingest all documents from a server-side directory.

**Request:**
```json
{
  "directory_path": "/app/data/synthetic_docs",
  "recursive": true,
  "workers": 4
}
```

**Response:**
```json
{
  "total_files": 10000,
  "successful": 9987,
  "failed": 13,
  "total_chunks": 384210,
  "duration_seconds": 1847.3,
  "errors": [
    {"file": "corrupt.pdf", "error": "Failed to parse: encrypted PDF"}
  ]
}
```

#### `GET /api/v1/documents`

List all ingested documents.

**Query Parameters:**
- `page` (int, default: 1)
- `page_size` (int, default: 50, max: 200)
- `search` (str, optional) — filter by filename

**Response:**
```json
{
  "documents": [
    {
      "doc_id": "abc123",
      "filename": "report_2024.pdf",
      "file_type": "pdf",
      "chunk_count": 47,
      "ingested_at": "2024-01-15T10:30:00Z",
      "size_bytes": 1048576
    }
  ],
  "total": 1250,
  "page": 1,
  "page_size": 50
}
```

#### `DELETE /api/v1/documents/{doc_id}`

Delete a document and all its chunks from the index.

**Response:**
```json
{
  "doc_id": "abc123",
  "deleted_chunks": 47,
  "status": "deleted"
}
```

---

### Query

#### `POST /api/v1/query/stream`

Query the RAG system with streaming SSE response.

**Request:**
```json
{
  "query": "What are the key findings in the 2024 annual report?",
  "session_id": "sess_xyz789",
  "top_k": 5
}
```

**Response:** `text/event-stream`

Each event is a JSON payload on a `data:` line:
```
data: {"token": "The ", "done": false}

data: {"token": "key ", "done": false}

data: {"token": "findings", "done": false}

data: {"token": "...", "done": false}

data: {"token": "", "done": true, "metadata": {
  "citations": [
    {
      "id": "chunk_001",
      "source": "annual_report_2024.pdf",
      "page": 12,
      "text_snippet": "Revenue grew by 23% year-over-year...",
      "relevance_score": 0.94
    }
  ],
  "hallucination_score": 0.12,
  "hallucination_flagged": false,
  "model_used": "gemini-1.5-flash",
  "duration_ms": 1847,
  "retrieval_scores": [0.94, 0.87, 0.83, 0.79, 0.71],
  "session_id": "sess_xyz789"
}}

```

**JavaScript SSE Client Example:**
```javascript
const response = await fetch('/api/v1/query/stream', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({query: 'Your question', session_id: 'sess_xyz'})
});

const reader = response.body.getReader();
const decoder = new TextDecoder();

while (true) {
  const {done, value} = await reader.read();
  if (done) break;
  
  const text = decoder.decode(value);
  const lines = text.split('\n');
  for (const line of lines) {
    if (line.startsWith('data: ')) {
      const data = JSON.parse(line.slice(6));
      if (!data.done) {
        console.log(data.token); // stream token
      } else {
        console.log(data.metadata); // final metadata
      }
    }
  }
}
```

#### `POST /api/v1/query`

Non-streaming query (waits for full response).

**Request:**
```json
{
  "query": "What is machine learning?",
  "session_id": "sess_xyz789",
  "top_k": 5
}
```

**Response:**
```json
{
  "answer": "Machine learning is a subset of artificial intelligence...",
  "citations": [...],
  "hallucination_score": 0.08,
  "hallucination_flagged": false,
  "model_used": "gemini-1.5-flash",
  "duration_ms": 2340,
  "session_id": "sess_xyz789"
}
```

---

### Sessions

#### `POST /api/v1/sessions`

Create a new conversation session.

**Response:**
```json
{
  "id": "sess_abc123",
  "created_at": "2024-01-15T10:30:00Z",
  "title": "New Conversation"
}
```

#### `GET /api/v1/sessions`

List all sessions.

**Response:**
```json
{
  "sessions": [
    {
      "id": "sess_abc123",
      "title": "What is RAG?",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T11:45:00Z",
      "message_count": 6
    }
  ]
}
```

#### `GET /api/v1/sessions/{session_id}`

Get session details with message history.

**Response:**
```json
{
  "id": "sess_abc123",
  "title": "What is RAG?",
  "created_at": "2024-01-15T10:30:00Z",
  "messages": [
    {
      "id": "msg_001",
      "role": "user",
      "content": "What is RAG?",
      "timestamp": "2024-01-15T10:30:00Z"
    },
    {
      "id": "msg_002",
      "role": "assistant",
      "content": "RAG (Retrieval-Augmented Generation) is...",
      "timestamp": "2024-01-15T10:30:02Z",
      "metadata": {
        "citations": [...],
        "hallucination_score": 0.05,
        "model_used": "gemini-1.5-flash"
      }
    }
  ]
}
```

#### `DELETE /api/v1/sessions/{session_id}`

Delete a session and all its messages.

**Response:**
```json
{"status": "deleted", "session_id": "sess_abc123"}
```

---

## Error Responses

All error responses follow this format:
```json
{
  "detail": "Human-readable error message",
  "error_code": "INJECTION_DETECTED",
  "request_id": "req_abc123"
}
```

| HTTP Code | Meaning |
|-----------|---------|
| 400 | Bad request (invalid input) |
| 404 | Resource not found |
| 422 | Validation error |
| 429 | Rate limit exceeded |
| 451 | Query blocked (injection detected) |
| 500 | Internal server error |
| 503 | Service unavailable (LLM down) |

---

## Rate Limits

- Default: **60 requests/minute** per IP
- Rate limit headers included in all responses:
  - `X-RateLimit-Limit: 60`
  - `X-RateLimit-Remaining: 45`
  - `X-RateLimit-Reset: 1705312260`

---

## Interactive API Docs

The FastAPI backend auto-generates interactive API docs at:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`
