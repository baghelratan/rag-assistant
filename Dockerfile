# ==========================================
# Stage 1: Build the React Frontend
# ==========================================
FROM node:20-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
# We pass an empty VITE_API_URL so the frontend makes relative API requests
# directly to the host serving the page. This eliminates CORS configuration issues.
ENV VITE_API_URL=""
RUN npm run build

# ==========================================
# Stage 2: Build the FastAPI Backend & Assemble
# ==========================================
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpoppler-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

# Install backend dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend codebase
COPY backend/ .

# Copy built frontend assets to the directory served statically by FastAPI
COPY --from=frontend-builder /frontend/dist /frontend/dist

# Ensure required persistent storage directories exist
RUN mkdir -p data/chroma data/bm25 data/cache data/synthetic_docs

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Run backend which handles API routing and serves the static frontend
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
