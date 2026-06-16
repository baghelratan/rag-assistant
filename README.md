# 🤖 Your Friendly Neighborhood RAG Assistant

Imagine having an AI assistant that can read tens of thousands of your private PDFs, HTML pages, and CSV spreadsheets, answer your questions instantly with precise citations, and do it all without leaking your data or running up a massive bill.

That's exactly what this project is. It's a production-grade, local-first Retrieval-Augmented Generation (RAG) assistant designed for real-world document intelligence. 

No more feeding sensitive files into black-box APIs. No more guessing where the AI got its answers. Just raw, private, verifiable document search and chat.

---

## ✨ What Makes This System Special?

Instead of just hooking up a standard vector database to an LLM, we built this with production reliability and visual elegance in mind. Here's a tour of the magic:

*   📂 **Reads Anything (Without Complaining)**: Drag and drop PDFs (parsed page-by-page), raw HTML web pages (cleaned of scripts and boilerplate), or dense CSV tables (indexed using sliding context windows so row relationships aren't lost).
*   🔍 **Dual-Brain Hybrid Search**: We don't just search by keywords or just by concepts. We run a concept search (dense vectors using ChromaDB) and a keyword search (sparse index using BM25 Okapi) in parallel, then fuse them using **Reciprocal Rank Fusion (RRF)**. This gives you the best of both worlds.
*   🎯 **Local Reranking (Double-Checking)**: To keep API costs down and accuracy high, we retrieve the top 20 documents, then use a tiny, fast cross-encoder model running *locally* on your machine to score and narrow them down to the top 5 most relevant.
*   🧠 **Conversation Memory**: It keeps track of the context. Using a SQLite database behind the scenes, it remembers the last 10 turns of your conversation so you can ask natural follow-up questions.
*   🛡️ **Security First (Prompt Injection Defense)**: Built-in scanners actively watch out for malicious prompt injections (like "ignore previous instructions") and block them before they reach the LLM.
*   ⚠️ **Keeping the AI Honest (Hallucination Detector)**: Every time the AI generates a response, a local model evaluates how well the answer aligns with the source documents. If it detects a hallucination, it flags it instantly.
*   📊 **Visual Telemetry**: A beautiful glassmorphism dark-theme dashboard with interactive latency dials, cache efficiency monitors, and a citations explorer.

---

## 🚀 Getting Started

Getting set up is easy. Choose whichever route fits your workflow:

### Option 1: The Fast Route (Docker Compose) 🐳

If you have Docker installed, you can spin up the entire system (Frontend, Backend, Prometheus, and Grafana) in about 60 seconds.

1.  **Clone or navigate** to the project directory.
2.  **Copy the environment file template**:
    ```bash
    cp .env.example .env
    ```
3.  **Open the `.env` file** and add your Gemini API key (you can grab a free one at [makersuite.google.com](https://makersuite.google.com/app/apikey)):
    ```env
    GEMINI_API_KEY=your_key_here
    ```
4.  **Launch the containers**:
    ```bash
    docker-compose up -d
    ```

Once it's up, you're ready to go:
*   🎨 **Frontend Dashboard**: `http://localhost:3000`
*   ⚙️ **Backend API Docs**: `http://localhost:8000/docs`
*   📈 **Prometheus Metrics**: `http://localhost:9090`
*   📊 **Grafana Observability**: `http://localhost:3001` (Sign in with username `admin` and password `admin123`)

---

### Option 2: The Hands-On Route (Local Dev Setup) 💻

If you want to run the code natively on your machine to play around with it:

#### 1. Spin up the Backend 🐍
1. Navigate to the backend directory:
   ```bash
   cd backend/
   ```
2. Create and activate a Python virtual environment:
   * **macOS/Linux**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   * **Windows**:
     ```powershell
     python -m venv venv
     .\venv\Scripts\Activate.ps1
     ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Copy the environment config and add your Gemini API key to `.env`:
   ```bash
   cp ../.env.example .env
   ```
5. Create the required directories for local databases and caches:
   ```bash
   mkdir -p data/chroma data/bm25 data/cache data/synthetic_docs
   ```
6. Start the server:
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```

#### 2. Spin up the Frontend ⚛️
1. Open a new terminal window and navigate to the frontend:
   ```bash
   cd frontend/
   ```
2. Install the frontend packages:
   ```bash
   npm install
   ```
3. Configure the local API endpoint:
   ```bash
   echo "VITE_API_URL=http://127.0.0.1:8000" > .env
   ```
4. Start the development server:
   ```bash
   npm run dev
   ```
   Now, open your browser and head to `http://127.0.0.1:3000`!

---

## 📈 Testing with Massive Datasets

Want to see how the system handles 10,000+ documents? We have included scripts to generate synthetic files and ingest them in bulk to test the scaling capabilities:

```bash
cd backend/

# 1. Generate 10,000 synthetic files (PDFs, HTML, and CSVs)
python scripts/generate_synthetic_data.py --count 10000 --output ./data/synthetic_docs

# 2. Ingest them all using 4 worker processes
python scripts/bulk_ingest.py --dir ./data/synthetic_docs --workers 4
```

You can also trigger bulk ingestion directly via an API request if you prefer:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/ingest/bulk \
  -H "Content-Type: application/json" \
  -d '{"directory_path": "/app/data/synthetic_docs", "recursive": true}'
```

---

## 🧪 Testing the Codebase

All features are covered by a comprehensive suite of unit and integration tests. To run them:

```bash
cd backend/
pytest tests/ -v --tb=short
```

To run them with a detailed HTML coverage report:
```bash
pytest tests/ --cov=app --cov-report=html
```

---

## 🏗️ Under the Hood

The architecture is built cleanly around standard Python and React tools. Here's a look at the project layout:

```
rag/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI application router and setup
│   │   ├── config.py               # Pydantic environment configuration
│   │   ├── api/routes/             # API endpoints (ingestion, sessions, query)
│   │   ├── ingestion/              # Ingestion engine (PDF, HTML, CSV parsers and recursive character chunker)
│   │   ├── retrieval/              # Smart hybrid retrieval (ChromaDB vector store, BM25 key-store, Reranker)
│   │   ├── generation/             # LLM orchestration, prompts, streams, and hallucination checks
│   │   ├── session/                # SQLite conversation memory
│   │   ├── security/               # Prompt injection defense and rate limiting
│   │   └── observability/          # Prometheus metrics exporter
│   ├── scripts/
│   │   ├── generate_synthetic_data.py  # Script to generate mock files for stress testing
│   │   └── bulk_ingest.py              # Command-line bulk ingestion script
│   ├── tests/                      # Pytest suite
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/             # React UI components (Glassmorphism layout, citations panel, etc.)
│   │   ├── hooks/                  # Custom hooks (e.g. SSE stream, session handlers)
│   │   └── services/               # REST API clients
│   └── Dockerfile
```

For a deeper dive into design choices, check out [docs/architecture.md](docs/architecture.md) and [docs/evaluation_report.md](docs/evaluation_report.md).

---

## 📄 License

This project is licensed under the MIT License. Feel free to copy, modify, and build upon it!
