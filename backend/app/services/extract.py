"""bytes -> text. No FastAPI here: raises ExtractionFailedError /
UnsupportedFileError, which the router translates.

File type is checked by magic bytes, never by filename extension, per
DESIGN.md's security section.
"""

import io

from docx import Document
from pypdf import PdfReader

from app.core.exceptions import ExtractionFailedError, UnsupportedFileError

# Minimum characters of extracted text before we trust it. Below this the
# file is almost certainly a scanned image with no text layer.
MIN_TEXT_LENGTH = 100

_PDF_MAGIC = b"%PDF-"
_DOCX_MAGIC = b"PK\x03\x04"  # DOCX is a zip archive


def _sniff(data: bytes) -> str:
    """Returns 'pdf' or 'docx' based on the file's magic bytes, never the
    filename extension."""
    if data.startswith(_PDF_MAGIC):
        return "pdf"
    if data.startswith(_DOCX_MAGIC):
        return "docx"
    raise UnsupportedFileError()


def _extract_pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_docx(data: bytes) -> str:
    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs)


def to_text(data: bytes) -> str:
    """Extracts plain text from PDF or DOCX bytes.

    Raises UnsupportedFileError if the bytes are neither, and
    ExtractionFailedError if parsing succeeds but yields no usable text
    (the scanned-image case).
    """
    kind = _sniff(data)
    text = _extract_pdf(data) if kind == "pdf" else _extract_docx(data)
    text = text.strip()

    if len(text) < MIN_TEXT_LENGTH:
        raise ExtractionFailedError()

    return text
