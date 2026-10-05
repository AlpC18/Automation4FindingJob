"""
PDF Verification Tool — ATS Text Layer & Page Count Validator
Adapted from MadsLorentzen/ai-job-search verify_pdf.py

Verifies generated CV/Cover Letter PDFs:
1. Page count matches expected (e.g., CV = 2 pages, Cover Letter = 1 page)
2. Text layer is extractable (ATS parsers read embedded text, not rendered page)
3. Required keywords appear in the text layer
4. No corrupted glyphs (cid:*, replacement chars)

Usage:
    from backend.app.tools.verify_pdf import verify_pdf, VerificationError
    extractor, text, pages = verify_pdf(Path("cv.pdf"), expected_pages=2, min_chars=100)
"""

import argparse
import re
import subprocess
import sys
import unicodedata
from pathlib import Path
from typing import List, Optional, Tuple


class VerificationError(Exception):
    """Raised when a generated PDF does not satisfy its checks."""


def run_tool(command: list) -> str:
    """Run an external command and return stdout."""
    try:
        return subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).stdout
    except FileNotFoundError as exc:
        raise VerificationError(
            f"Required command '{command[0]}' was not found. "
            "Install pypdf (`pip install pypdf`) or poppler-utils "
            "(macOS: brew install poppler, Debian/Ubuntu: apt install poppler-utils)"
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or "").strip() or (exc.stdout or "").strip()
        detail = detail or "command failed"
        raise VerificationError(f"{command[0]} could not read the PDF: {detail}") from exc


def parse_page_count(pdfinfo_output: str) -> int:
    """Parse page count from pdfinfo output."""
    match = re.search(r"^Pages:\s+(\d+)\s*$", pdfinfo_output, re.MULTILINE)
    if not match:
        raise VerificationError("pdfinfo output did not contain a page count")
    return int(match.group(1))


# LaTeX typographic substitutions mapped back for --contains matching
TYPOGRAPHIC_MAP = {
    "\u2019": "'",    # Right single quote → apostrophe
    "\u2018": "'",    # Left single quote → apostrophe
    "\u201c": '"',    # Left double quote
    "\u201d": '"',    # Right double quote
    "\u2013": "-",    # En dash
    "\u2014": "--",   # Em dash
    "\u00a0": " ",    # Non-breaking space
}


def normalize_text(text: str) -> str:
    """Normalize text for comparison, handling LaTeX typographic substitutions."""
    text = unicodedata.normalize("NFC", text)
    for fancy, plain in TYPOGRAPHIC_MAP.items():
        text = text.replace(fancy, plain)
    return " ".join(text.split()).lower()


def extract_text_pypdf(pdf_path: Path) -> Tuple[str, int]:
    """Extract text and page count using pypdf."""
    try:
        from pypdf import PdfReader
    except ImportError:
        raise VerificationError(
            "pypdf is not installed. Install with: pip install pypdf"
        )

    reader = PdfReader(str(pdf_path))
    pages = len(reader.pages)
    text_parts = []
    for page in reader.pages:
        text_parts.append(page.extract_text() or "")
    return "\n".join(text_parts), pages


def extract_text_pdftotext(pdf_path: Path) -> Tuple[str, int]:
    """Extract text using poppler's pdftotext and pdfinfo."""
    text = run_tool(["pdftotext", "-layout", "-enc", "UTF-8", str(pdf_path), "-"])
    info = run_tool(["pdfinfo", str(pdf_path)])
    pages = parse_page_count(info)
    return text, pages


def verify_pdf(
    pdf_path: Path,
    expected_pages: Optional[int] = None,
    min_chars: int = 1,
    contains: Optional[List[str]] = None,
    dump_text: Optional[Path] = None,
) -> Tuple[str, str, int]:
    """
    Verify a PDF's page count and ATS-readable text layer.

    Returns:
        (extractor_name, extracted_text, page_count)

    Raises:
        VerificationError if any check fails.
    """
    if not pdf_path.is_file():
        raise VerificationError(f"File not found: {pdf_path}")

    # Try pypdf first, fall back to pdftotext
    extractor = "pypdf"
    try:
        text, pages = extract_text_pypdf(pdf_path)
    except (VerificationError, Exception):
        extractor = "pdftotext"
        try:
            text, pages = extract_text_pdftotext(pdf_path)
        except VerificationError:
            raise VerificationError(
                "Neither pypdf nor pdftotext could extract text. "
                "Install one: pip install pypdf or brew install poppler"
            )

    # Dump text if requested
    if dump_text:
        dump_text.write_text(text, encoding="utf-8")

    # Check page count
    if expected_pages is not None and pages != expected_pages:
        raise VerificationError(
            f"Expected {expected_pages} page(s), got {pages}"
        )

    # Check minimum character count (non-whitespace)
    non_ws = len(re.sub(r"\s", "", text))
    if non_ws < min_chars:
        raise VerificationError(
            f"Text layer has only {non_ws} non-whitespace characters "
            f"(minimum: {min_chars}). PDF may be image-only or corrupted."
        )

    # Check for corrupted glyphs
    cid_matches = re.findall(r"\(cid:\d+\)", text)
    if cid_matches:
        raise VerificationError(
            f"Found {len(cid_matches)} corrupted glyph markers (cid:*) in text layer. "
            "Font embedding may be broken."
        )

    replacement_chars = text.count("\ufffd")
    if replacement_chars > 5:
        raise VerificationError(
            f"Found {replacement_chars} replacement characters (�) in text layer. "
            "Encoding issue detected."
        )

    # Check required keywords
    if contains:
        norm_text = normalize_text(text)
        missing = []
        for keyword in contains:
            if normalize_text(keyword) not in norm_text:
                missing.append(keyword)
        if missing:
            raise VerificationError(
                f"Required keywords missing from text layer: {missing}"
            )

    return extractor, text, pages


def verify_pdf_dict(
    pdf_path: str,
    expected_pages: Optional[int] = None,
    min_chars: int = 1,
    contains: Optional[List[str]] = None,
) -> dict:
    """API-friendly wrapper that returns a dict instead of raising."""
    try:
        extractor, text, pages = verify_pdf(
            Path(pdf_path), expected_pages, min_chars, contains
        )
        return {
            "status": "verified",
            "extractor": extractor,
            "pages": pages,
            "text_length": len(text),
            "non_whitespace_chars": len(re.sub(r"\s", "", text)),
        }
    except VerificationError as e:
        return {
            "status": "failed",
            "error": str(e),
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify a PDF's page count and ATS-readable text layer.")
    parser.add_argument("pdf", type=Path, help="PDF file to verify")
    parser.add_argument("--pages", type=int, help="Required exact page count")
    parser.add_argument("--min-chars", type=int, default=1, help="Minimum non-whitespace text-layer characters")
    parser.add_argument("--contains", action="append", default=[], help="Text that must appear in the text layer")
    parser.add_argument("--dump-text", type=Path, help="Write extracted text layer to this path")
    args = parser.parse_args()

    try:
        extractor, text, pages = verify_pdf(args.pdf, args.pages, args.min_chars, args.contains, args.dump_text)
        print(f"✅ Verified {args.pdf} (extractor: {extractor}, pages: {pages})")
    except VerificationError as exc:
        print(f"❌ Error: {args.pdf}: {exc}", file=sys.stderr)
        sys.exit(1)
