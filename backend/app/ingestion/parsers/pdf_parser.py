"""
PDF parser using PyMuPDF (fitz).
Extracts text page by page, preserves page numbers in metadata,
and handles encrypted PDFs gracefully.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def parse_pdf(file_path: str) -> List[Dict[str, Any]]:
    """
    Parse a PDF file and extract text per page.

    Args:
        file_path: Absolute or relative path to the PDF file.

    Returns:
        List of dicts with keys: {text, page, source}
    """
    path = Path(file_path)
    results: List[Dict[str, Any]] = []

    try:
        doc = fitz.open(str(path))
    except fitz.FileDataError as exc:
        logger.error("Failed to open PDF '%s': %s", file_path, exc)
        return results

    # Handle encrypted PDFs
    if doc.is_encrypted:
        success = doc.authenticate("")  # try empty password
        if not success:
            logger.warning("PDF '%s' is encrypted and could not be decrypted. Skipping.", file_path)
            doc.close()
            return results

    logger.info("Parsing PDF '%s' (%d pages)", path.name, doc.page_count)

    for page_num in range(doc.page_count):
        try:
            page = doc[page_num]
            # Extract text with layout preservation
            text = page.get_text("text")
            text = text.strip()

            if not text:
                logger.debug("Page %d of '%s' is empty, skipping.", page_num + 1, path.name)
                continue

            # Extract any embedded links on the page
            links = [link.get("uri", "") for link in page.get_links() if link.get("uri")]

            results.append(
                {
                    "text": text,
                    "page": page_num + 1,  # 1-indexed
                    "source": path.name,
                    "source_path": str(path.resolve()),
                    "total_pages": doc.page_count,
                    "links": links,
                }
            )
        except Exception as exc:
            logger.error("Error extracting page %d from '%s': %s", page_num + 1, file_path, exc)
            continue

    doc.close()
    logger.info("Extracted %d non-empty pages from '%s'", len(results), path.name)
    return results


def parse_pdf_bytes(content: bytes, filename: str) -> List[Dict[str, Any]]:
    """
    Parse PDF from raw bytes (e.g., uploaded via API).

    Args:
        content: Raw PDF bytes.
        filename: Original filename for metadata.

    Returns:
        List of dicts with keys: {text, page, source}
    """
    results: List[Dict[str, Any]] = []

    try:
        doc = fitz.open(stream=content, filetype="pdf")
    except fitz.FileDataError as exc:
        logger.error("Failed to parse PDF bytes for '%s': %s", filename, exc)
        return results

    if doc.is_encrypted:
        success = doc.authenticate("")
        if not success:
            logger.warning("PDF '%s' (bytes) is encrypted and could not be decrypted.", filename)
            doc.close()
            return results

    logger.info("Parsing PDF bytes '%s' (%d pages)", filename, doc.page_count)

    for page_num in range(doc.page_count):
        try:
            page = doc[page_num]
            text = page.get_text("text").strip()
            if not text:
                continue
            links = [link.get("uri", "") for link in page.get_links() if link.get("uri")]
            results.append(
                {
                    "text": text,
                    "page": page_num + 1,
                    "source": filename,
                    "source_path": filename,
                    "total_pages": doc.page_count,
                    "links": links,
                }
            )
        except Exception as exc:
            logger.error("Error on page %d of '%s': %s", page_num + 1, filename, exc)
            continue

    doc.close()
    return results
