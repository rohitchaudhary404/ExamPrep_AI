#!/usr/bin/env python3
"""Extract plain text from uploaded notes files (.txt, .md, .docx, .pdf)."""

import io
import os

MAX_TEXT_LEN = 200_000  # sanity cap


def extract_text(data, filename):
    """Return (text, filename) for the given raw bytes and original filename.

    Raises ValueError for unsupported/undecodable content.
    """
    ext = os.path.splitext(filename or "")[1].lower()

    if ext in (".txt", ".md", ".markdown", ".text", ""):
        text = _decode(data)

    elif ext == ".docx":
        import docx  # python-docx

        doc = docx.Document(io.BytesIO(data))
        parts = [p.text for p in doc.paragraphs if p.text and p.text.strip()]
        # also include table cell text
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text and cell.text.strip():
                        parts.append(cell.text)
        text = "\n".join(parts)

    elif ext == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = []
        for page in reader.pages:
            t = page.extract_text() or ""
            if t.strip():
                pages.append(t.strip())
        text = "\n\n".join(pages)

    else:
        raise ValueError(f"Unsupported file type '{ext}'. Use .txt, .md, .docx or .pdf.")

    text = text.strip()
    if not text:
        raise ValueError("Could not find any text in that file (it may be a scanned/image PDF).")
    if len(text) > MAX_TEXT_LEN:
        text = text[:MAX_TEXT_LEN] + "\n\n…(truncated)"
    return text


def _decode(data):
    for enc in ("utf-8", "utf-16", "latin-1", "cp1252"):
        try:
            return data.decode(enc).strip()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return data.decode("utf-8", errors="replace").strip()
