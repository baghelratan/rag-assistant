"""
Bulk ingestion CLI script.
Reads all PDF/HTML/CSV files from a directory recursively,
ingests via pipeline in parallel, and saves a JSON report.

Usage:
    python scripts/bulk_ingest.py --dir ./data/synthetic_docs --workers 4
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import List

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from tqdm import tqdm
except ImportError:
    print("Install tqdm: pip install tqdm")
    sys.exit(1)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("bulk_ingest")

_SUPPORTED_EXTENSIONS = {".pdf", ".html", ".htm", ".csv", ".txt", ".md"}


def collect_files(directory: str, recursive: bool = True) -> List[Path]:
    """Collect all supported files from a directory."""
    dir_path = Path(directory)
    if not dir_path.exists() or not dir_path.is_dir():
        raise ValueError(f"Directory not found: {directory}")

    if recursive:
        files = [
            f for f in dir_path.rglob("*")
            if f.is_file() and f.suffix.lower() in _SUPPORTED_EXTENSIONS
        ]
    else:
        files = [
            f for f in dir_path.iterdir()
            if f.is_file() and f.suffix.lower() in _SUPPORTED_EXTENSIONS
        ]

    return sorted(files)


async def run_bulk_ingest(
    directory: str,
    workers: int = 4,
    output_report: str = "ingestion_report.json",
    recursive: bool = True,
) -> dict:
    """
    Run bulk ingestion with parallel workers.

    Args:
        directory: Input directory.
        workers: Concurrency level (asyncio semaphore).
        output_report: Path for the JSON report.
        recursive: Whether to scan subdirectories.

    Returns:
        Summary report dict.
    """
    from app.config import settings
    settings.ensure_dirs()

    from app.ingestion.embedder import Embedder
    from app.retrieval.vector_store import VectorStore
    from app.retrieval.bm25_store import BM25Store
    from app.ingestion.pipeline import IngestionPipeline

    logger.info("Initializing components…")
    embedder = Embedder()
    vector_store = VectorStore()
    bm25_store = BM25Store()
    pipeline = IngestionPipeline(embedder, vector_store, bm25_store)

    files = collect_files(directory, recursive=recursive)
    if not files:
        logger.warning("No supported files found in '%s'", directory)
        return {"total": 0, "succeeded": 0, "failed": 0, "results": []}

    logger.info("Found %d files to ingest (workers=%d)", len(files), workers)

    sem = asyncio.Semaphore(workers)
    results = []
    pbar = tqdm(total=len(files), desc="Ingesting", unit="file", dynamic_ncols=True)

    async def _ingest_one(file_path: Path) -> dict:
        async with sem:
            t0 = time.perf_counter()
            result = await pipeline.ingest_file(str(file_path))
            duration = time.perf_counter() - t0
            pbar.update(1)
            pbar.set_postfix_str(f"Last: {file_path.name[:25]}")
            return {
                "filename": result.filename,
                "doc_id": result.doc_id,
                "chunk_count": result.chunk_count,
                "duration_ms": round(duration * 1000, 2),
                "status": result.status,
                "error": result.error,
            }

    tasks = [_ingest_one(f) for f in files]
    ingestion_results = await asyncio.gather(*tasks)
    pbar.close()

    results = list(ingestion_results)
    succeeded = sum(1 for r in results if r["status"] == "success")
    failed = len(results) - succeeded
    total_chunks = sum(r["chunk_count"] for r in results if r["status"] == "success")

    report = {
        "directory": str(directory),
        "total_files": len(files),
        "succeeded": succeeded,
        "failed": failed,
        "total_chunks_created": total_chunks,
        "results": results,
        "errors": [r for r in results if r["status"] == "error"],
    }

    # Save report
    report_path = Path(output_report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    logger.info(
        "Ingestion complete: %d succeeded, %d failed, %d total chunks",
        succeeded, failed, total_chunks,
    )
    logger.info("Report saved to: %s", report_path)

    return report


def main():
    parser = argparse.ArgumentParser(description="Bulk ingest documents into the RAG system")
    parser.add_argument("--dir", required=True, help="Directory containing documents to ingest")
    parser.add_argument("--workers", type=int, default=4, help="Number of concurrent ingestion workers")
    parser.add_argument("--report", default="ingestion_report.json", help="Output JSON report path")
    parser.add_argument("--no-recursive", action="store_true", help="Don't scan subdirectories")
    args = parser.parse_args()

    t0 = time.time()
    report = asyncio.run(
        run_bulk_ingest(
            directory=args.dir,
            workers=args.workers,
            output_report=args.report,
            recursive=not args.no_recursive,
        )
    )
    total_time = time.time() - t0

    print(f"\n{'='*50}")
    print(f"BULK INGESTION COMPLETE")
    print(f"{'='*50}")
    print(f"  Files:      {report['total_files']}")
    print(f"  Succeeded:  {report['succeeded']}")
    print(f"  Failed:     {report['failed']}")
    print(f"  Chunks:     {report['total_chunks_created']}")
    print(f"  Duration:   {total_time:.1f}s")
    print(f"  Report:     {args.report}")


if __name__ == "__main__":
    main()
