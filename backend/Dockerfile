FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpoppler-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p data/chroma data/bm25 data/cache data/synthetic_docs

EXPOSE 8000

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1"]
