"""
HTML parser using BeautifulSoup4.
Strips scripts/styles, extracts main content, and preserves heading structure.
"""

import logging
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

# Tags whose content should be completely removed
_NOISE_TAGS = [
    "script", "style", "noscript", "head", "nav", "footer",
    "aside", "advertisement", "iframe", "svg", "canvas",
]

# Tags considered "main content" containers (checked in order)
_MAIN_CONTENT_SELECTORS = [
    "article",
    "main",
    '[role="main"]',
    "#main-content",
    ".main-content",
    ".content",
    ".post-content",
    ".entry-content",
    "body",
]


def _clean_soup(soup: BeautifulSoup) -> None:
    """Remove noise tags in-place."""
    for tag_name in _NOISE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()
    # Remove HTML comments
    for comment in soup.find_all(string=lambda text: isinstance(text, str) and text.startswith("<!--")):
        comment.extract()


def _extract_headings(soup: BeautifulSoup) -> Dict[str, List[str]]:
    """Extract all headings (h1-h6) and return them keyed by tag name."""
    headings: Dict[str, List[str]] = {}
    for level in range(1, 7):
        tag_name = f"h{level}"
        tags = soup.find_all(tag_name)
        texts = [t.get_text(separator=" ", strip=True) for t in tags if t.get_text(strip=True)]
        if texts:
            headings[tag_name] = texts
    return headings


def _find_main_content(soup: BeautifulSoup) -> Tag:
    """Return the best candidate Tag for main content."""
    for selector in _MAIN_CONTENT_SELECTORS:
        try:
            found = soup.select_one(selector)
            if found:
                return found
        except Exception:
            continue
    return soup.body or soup  # type: ignore[return-value]


def _split_by_heading(content_tag: Tag) -> List[Dict[str, str]]:
    """
    Split content into sections based on headings.
    Returns list of {section_title, text}.
    """
    sections: List[Dict[str, str]] = []
    current_heading = "Introduction"
    current_texts: List[str] = []

    for child in content_tag.descendants:
        if not isinstance(child, Tag):
            continue
        if child.name in {f"h{i}" for i in range(1, 7)}:
            # Save previous section
            text = " ".join(current_texts).strip()
            if text:
                sections.append({"section_title": current_heading, "text": text})
            current_heading = child.get_text(separator=" ", strip=True)
            current_texts = []
        elif child.name in {"p", "li", "td", "th", "blockquote", "pre", "code"}:
            t = child.get_text(separator=" ", strip=True)
            if t:
                current_texts.append(t)

    # Last section
    text = " ".join(current_texts).strip()
    if text:
        sections.append({"section_title": current_heading, "text": text})

    return sections


def parse_html(file_path: str) -> List[Dict[str, Any]]:
    """
    Parse an HTML file and extract structured content.

    Args:
        file_path: Path to the HTML file.

    Returns:
        List of dicts: {text, section, source, url}
    """
    path = Path(file_path)
    results: List[Dict[str, Any]] = []

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            raw_html = f.read()
    except OSError as exc:
        logger.error("Cannot read HTML file '%s': %s", file_path, exc)
        return results

    return _parse_html_string(raw_html, source=path.name, source_path=str(path.resolve()))


def parse_html_bytes(content: bytes, filename: str, url: str = "") -> List[Dict[str, Any]]:
    """
    Parse HTML from raw bytes.

    Args:
        content: Raw HTML bytes.
        filename: Original filename for metadata.
        url: Optional source URL.

    Returns:
        List of dicts: {text, section, source, url}
    """
    raw_html = content.decode("utf-8", errors="replace")
    return _parse_html_string(raw_html, source=filename, source_path=filename, url=url)


def _parse_html_string(
    raw_html: str,
    source: str,
    source_path: str,
    url: str = "",
) -> List[Dict[str, Any]]:
    """Core HTML parsing logic shared by file and bytes parsers."""
    results: List[Dict[str, Any]] = []

    try:
        soup = BeautifulSoup(raw_html, "lxml")
    except Exception:
        soup = BeautifulSoup(raw_html, "html.parser")

    _clean_soup(soup)
    headings = _extract_headings(soup)
    main_content = _find_main_content(soup)

    # Try section-based splitting first
    sections = _split_by_heading(main_content)

    if not sections:
        # Fallback: get all visible text
        full_text = main_content.get_text(separator=" ", strip=True)
        full_text = re.sub(r"\s{2,}", " ", full_text).strip()
        if full_text:
            sections = [{"section_title": "Main Content", "text": full_text}]

    # Build result dicts
    h1_list = headings.get("h1", [])
    page_title = h1_list[0] if h1_list else source

    for sec in sections:
        text = re.sub(r"\s{2,}", " ", sec["text"]).strip()
        if len(text) < 20:  # skip trivially short sections
            continue
        results.append(
            {
                "text": text,
                "section": sec["section_title"],
                "source": source,
                "source_path": source_path,
                "url": url,
                "page_title": page_title,
                "headings": headings,
            }
        )

    logger.info("Parsed HTML '%s' → %d sections", source, len(results))
    return results
