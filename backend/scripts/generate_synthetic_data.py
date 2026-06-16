"""
Synthetic data generator: creates 10,000+ documents (PDF, HTML, CSV)
using Faker for realistic content.

Usage:
    python scripts/generate_synthetic_data.py --count 10000 --output ./data/synthetic_docs
"""

import argparse
import json
import os
import random
import sys
from pathlib import Path
from typing import List

try:
    from faker import Faker
    from fpdf import FPDF
    from tqdm import tqdm
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install: pip install faker fpdf2 tqdm")
    sys.exit(1)

fake = Faker()
Faker.seed(42)
random.seed(42)


# ---------------------------------------------------------------------------
# PDF generator
# ---------------------------------------------------------------------------

_PDF_TEMPLATES = ["article", "report", "technical_doc", "research_paper"]


def _generate_pdf(output_dir: Path, index: int) -> Path:
    """Generate a single synthetic PDF document."""
    doc_type = random.choice(_PDF_TEMPLATES)
    title = fake.catch_phrase()
    author = fake.name()
    date = fake.date_this_decade()

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 16)
    pdf.multi_cell(0, 10, title, align="C")
    pdf.ln(5)

    # Author & Date
    pdf.set_font("Helvetica", "I", 11)
    pdf.cell(0, 8, f"By {author} | {date}", align="C")
    pdf.ln(10)

    # Abstract
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Abstract")
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, fake.paragraph(nb_sentences=5))
    pdf.ln(5)

    # Sections
    num_sections = random.randint(3, 8)
    for sec_num in range(1, num_sections + 1):
        sec_title = fake.bs().title()
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 9, f"{sec_num}. {sec_title}")
        pdf.ln(5)
        pdf.set_font("Helvetica", "", 11)
        num_paragraphs = random.randint(2, 5)
        for _ in range(num_paragraphs):
            para = fake.paragraph(nb_sentences=random.randint(4, 8))
            pdf.multi_cell(0, 7, para)
            pdf.ln(3)

    # Conclusion
    pdf.set_font("Helvetica", "B", 13)
    pdf.cell(0, 9, "Conclusion")
    pdf.ln(5)
    pdf.set_font("Helvetica", "", 11)
    pdf.multi_cell(0, 7, fake.paragraph(nb_sentences=4))

    filename = f"doc_{doc_type}_{index:06d}.pdf"
    filepath = output_dir / "pdfs" / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(filepath))
    return filepath


# ---------------------------------------------------------------------------
# HTML generator
# ---------------------------------------------------------------------------

_HTML_TEMPLATES = ["news", "wiki", "blog", "product"]


def _generate_html(output_dir: Path, index: int) -> Path:
    """Generate a single synthetic HTML document."""
    template = random.choice(_HTML_TEMPLATES)
    title = fake.sentence(nb_words=6).rstrip(".")
    author = fake.name()
    date = fake.date_this_year()
    category = fake.word().title()

    sections = []
    for _ in range(random.randint(3, 6)):
        h2 = fake.bs().title()
        paragraphs = "\n".join(
            f"<p>{fake.paragraph(nb_sentences=random.randint(3, 7))}</p>"
            for _ in range(random.randint(2, 4))
        )
        sections.append(f"<h2>{h2}</h2>\n{paragraphs}")

    sections_html = "\n\n".join(sections)

    tags_html = " ".join(
        f'<span class="tag">{fake.word()}</span>'
        for _ in range(random.randint(3, 7))
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="description" content="{fake.sentence(nb_words=12)}">
    <title>{title}</title>
</head>
<body>
<nav><a href="/">Home</a> | <a href="/category/{category.lower()}">{category}</a></nav>
<main>
    <article>
        <h1>{title}</h1>
        <p class="meta">By <strong>{author}</strong> | Published: {date} | Category: {category}</p>
        <p class="intro">{fake.paragraph(nb_sentences=3)}</p>

        {sections_html}

        <div class="tags">{tags_html}</div>
    </article>
</main>
<footer>
    <p>&copy; {date[:4]} {fake.company()}. All rights reserved.</p>
</footer>
</body>
</html>"""

    filename = f"page_{template}_{index:06d}.html"
    filepath = output_dir / "html" / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(html, encoding="utf-8")
    return filepath


# ---------------------------------------------------------------------------
# CSV generator
# ---------------------------------------------------------------------------

_CSV_SCHEMAS = [
    {
        "name": "employees",
        "columns": ["id", "name", "department", "salary", "hire_date", "email", "city"],
        "generators": [
            lambda: str(fake.unique.random_int(1000, 9999)),
            fake.name,
            lambda: random.choice(["Engineering", "Marketing", "Sales", "HR", "Finance", "Product"]),
            lambda: str(random.randint(50000, 200000)),
            lambda: str(fake.date_this_decade()),
            fake.email,
            fake.city,
        ],
    },
    {
        "name": "products",
        "columns": ["sku", "name", "category", "price", "stock", "description", "rating"],
        "generators": [
            lambda: fake.bothify("??-####"),
            lambda: fake.catch_phrase(),
            lambda: random.choice(["Electronics", "Books", "Clothing", "Home", "Sports"]),
            lambda: f"{random.uniform(5.0, 999.99):.2f}",
            lambda: str(random.randint(0, 1000)),
            lambda: fake.sentence(nb_words=10),
            lambda: f"{random.uniform(1.0, 5.0):.1f}",
        ],
    },
    {
        "name": "research_data",
        "columns": ["sample_id", "date", "experiment", "value", "unit", "researcher", "notes"],
        "generators": [
            lambda: fake.bothify("S-########"),
            lambda: str(fake.date_this_year()),
            lambda: fake.bs(),
            lambda: f"{random.uniform(0.001, 99.999):.3f}",
            lambda: random.choice(["mg/L", "ppm", "°C", "bar", "mol/L"]),
            fake.name,
            lambda: fake.sentence(nb_words=8),
        ],
    },
]


def _generate_csv(output_dir: Path, index: int) -> Path:
    """Generate a single synthetic CSV file."""
    schema = random.choice(_CSV_SCHEMAS)
    num_rows = random.randint(50, 500)

    rows = [",".join(schema["columns"])]
    for _ in range(num_rows):
        row = [gen().replace(",", ";").replace("\n", " ") for gen in schema["generators"]]
        rows.append(",".join(row))

    filename = f"data_{schema['name']}_{index:06d}.csv"
    filepath = output_dir / "csv" / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text("\n".join(rows), encoding="utf-8")
    return filepath


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate synthetic documents for RAG testing")
    parser.add_argument("--count", type=int, default=10000, help="Total documents to generate")
    parser.add_argument("--output", type=str, default="./data/synthetic_docs", help="Output directory")
    parser.add_argument("--pdf-ratio", type=float, default=0.50, help="Fraction that are PDFs")
    parser.add_argument("--html-ratio", type=float, default=0.30, help="Fraction that are HTML")
    args = parser.parse_args()

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    total = args.count
    n_pdf = int(total * args.pdf_ratio)
    n_html = int(total * args.html_ratio)
    n_csv = total - n_pdf - n_html

    print(f"Generating {total} documents → {output_dir}")
    print(f"  PDFs: {n_pdf} | HTML: {n_html} | CSV: {n_csv}")

    results = {"pdf": [], "html": [], "csv": [], "errors": []}

    with tqdm(total=total, desc="Generating", unit="doc") as pbar:
        # PDFs
        for i in range(n_pdf):
            try:
                path = _generate_pdf(output_dir, i)
                results["pdf"].append(str(path))
            except Exception as exc:
                results["errors"].append({"type": "pdf", "index": i, "error": str(exc)})
            pbar.update(1)

        # HTML
        for i in range(n_html):
            try:
                path = _generate_html(output_dir, i)
                results["html"].append(str(path))
            except Exception as exc:
                results["errors"].append({"type": "html", "index": i, "error": str(exc)})
            pbar.update(1)

        # CSV
        for i in range(n_csv):
            try:
                path = _generate_csv(output_dir, i)
                results["csv"].append(str(path))
            except Exception as exc:
                results["errors"].append({"type": "csv", "index": i, "error": str(exc)})
            pbar.update(1)

    # Write manifest
    manifest = {
        "total_generated": len(results["pdf"]) + len(results["html"]) + len(results["csv"]),
        "pdf_count": len(results["pdf"]),
        "html_count": len(results["html"]),
        "csv_count": len(results["csv"]),
        "error_count": len(results["errors"]),
        "errors": results["errors"][:20],  # first 20 errors
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\n✓ Generated {manifest['total_generated']} documents")
    print(f"  PDF: {manifest['pdf_count']}, HTML: {manifest['html_count']}, CSV: {manifest['csv_count']}")
    print(f"  Errors: {manifest['error_count']}")
    print(f"  Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
