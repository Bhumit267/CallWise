"""File loaders for plain text, Markdown, and PDF documents."""

import os
from pathlib import Path
from typing import Tuple
from pypdf import PdfReader


def load_text_file(file_path: str) -> str:
    """Read a plain text or Markdown file with fallback encodings."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue

    raise ValueError(f"Unable to decode text file with standard encodings: {file_path}")


def load_pdf_file(file_path: str) -> str:
    """Extract text from a PDF document using pypdf."""
    path = Path(file_path)
    if not path.is_file():
        raise FileNotFoundError(f"File not found: {file_path}")

    reader = PdfReader(str(path))
    extracted_pages = []

    for index, page in enumerate(reader.pages):
        page_text = page.extract_text() or ""
        if page_text.strip():
            extracted_pages.append(page_text.strip())

    if not extracted_pages:
        raise ValueError(f"PDF file contains no extractable text: {file_path}")

    return "\n\n".join(extracted_pages)


def load_file(file_path: str) -> Tuple[str, str]:
    """
    Load document content and infer title from filename.

    Returns:
        (content, title)
    """
    path = Path(file_path)
    ext = path.suffix.lower()
    title = path.stem.replace("_", " ").replace("-", " ").title()

    if ext in (".txt", ".md", ".markdown"):
        content = load_text_file(str(path))
    elif ext == ".pdf":
        content = load_pdf_file(str(path))
    else:
        raise ValueError(f"Unsupported file format '{ext}'. Supported formats: .txt, .md, .pdf")

    return content, title
