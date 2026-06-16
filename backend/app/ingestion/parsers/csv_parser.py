"""
CSV parser using pandas.
Converts rows to text representations and supports a sliding-window context mode.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _row_to_text(row: pd.Series, columns: List[str]) -> str:
    """Convert a single DataFrame row to a readable text string."""
    parts = []
    for col in columns:
        value = row[col]
        if pd.isna(value):
            continue
        parts.append(f"{col}: {value}")
    return ", ".join(parts)


def parse_csv(
    file_path: str,
    window_size: int = 1,
    window_overlap: int = 0,
) -> List[Dict[str, Any]]:
    """
    Parse a CSV file and convert rows to text.

    Args:
        file_path: Path to the CSV file.
        window_size: Number of rows to combine per chunk (sliding window).
        window_overlap: Number of rows to overlap between windows.

    Returns:
        List of dicts: {text, row_index, source, columns, total_rows}
    """
    path = Path(file_path)
    results: List[Dict[str, Any]] = []

    try:
        df = _load_dataframe(str(path))
    except Exception as exc:
        logger.error("Failed to parse CSV '%s': %s", file_path, exc)
        return results

    return _dataframe_to_records(df, source=path.name, source_path=str(path.resolve()),
                                  window_size=window_size, window_overlap=window_overlap)


def parse_csv_bytes(
    content: bytes,
    filename: str,
    window_size: int = 1,
    window_overlap: int = 0,
) -> List[Dict[str, Any]]:
    """
    Parse CSV from raw bytes.

    Args:
        content: Raw CSV bytes.
        filename: Original filename for metadata.
        window_size: Number of rows to combine per chunk.
        window_overlap: Number of rows to overlap between windows.

    Returns:
        List of dicts: {text, row_index, source, columns, total_rows}
    """
    import io

    try:
        df = _load_dataframe(io.BytesIO(content))
    except Exception as exc:
        logger.error("Failed to parse CSV bytes for '%s': %s", filename, exc)
        return []

    return _dataframe_to_records(df, source=filename, source_path=filename,
                                  window_size=window_size, window_overlap=window_overlap)


def _load_dataframe(source) -> pd.DataFrame:
    """Try common CSV encodings and separators."""
    for encoding in ("utf-8", "latin-1", "cp1252"):
        for sep in (",", ";", "\t", "|"):
            try:
                df = pd.read_csv(source, encoding=encoding, sep=sep, on_bad_lines="skip")
                if df.shape[1] > 1 or sep == ",":
                    # Reset buffer position if reading from BytesIO
                    if hasattr(source, "seek"):
                        source.seek(0)
                    return df
            except Exception:
                if hasattr(source, "seek"):
                    source.seek(0)
                continue
    raise ValueError(f"Could not parse CSV with any encoding/separator combination.")


def _dataframe_to_records(
    df: pd.DataFrame,
    source: str,
    source_path: str,
    window_size: int,
    window_overlap: int,
) -> List[Dict[str, Any]]:
    """Convert a DataFrame to a list of text-record dicts."""
    results: List[Dict[str, Any]] = []

    # Sanitize column names
    df.columns = [str(c).strip() for c in df.columns]
    columns = list(df.columns)
    total_rows = len(df)

    logger.info("Parsing CSV '%s': %d rows × %d cols", source, total_rows, len(columns))

    if window_size <= 1:
        # Single-row mode
        for idx, row in df.iterrows():
            text = _row_to_text(row, columns)
            if not text.strip():
                continue
            results.append(
                {
                    "text": text,
                    "row_index": int(idx),  # type: ignore[arg-type]
                    "source": source,
                    "source_path": source_path,
                    "columns": columns,
                    "total_rows": total_rows,
                }
            )
    else:
        # Sliding-window mode
        step = max(1, window_size - window_overlap)
        i = 0
        while i < total_rows:
            window_rows = df.iloc[i : i + window_size]
            texts = [_row_to_text(row, columns) for _, row in window_rows.iterrows()]
            combined = " | ".join(t for t in texts if t.strip())
            if combined:
                results.append(
                    {
                        "text": combined,
                        "row_index": i,
                        "row_end_index": min(i + window_size - 1, total_rows - 1),
                        "source": source,
                        "source_path": source_path,
                        "columns": columns,
                        "total_rows": total_rows,
                    }
                )
            i += step

    logger.info("Produced %d records from CSV '%s'", len(results), source)
    return results
