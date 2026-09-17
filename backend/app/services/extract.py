"""bytes -> text. No FastAPI here: raises ExtractionFailedError /
UnsupportedFileError, which the router translates.

File type is checked by magic bytes, never by filename extension, per
DESIGN.md's security section.
"""

import io
import zipfile

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
    # A "%PDF-" header with a broken body raises from deep inside pypdf
    # (PdfStreamError, PdfReadError, and the odd ValueError). Any of those
    # means the file is not usable, which is the same outcome as no text.
    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        raise ExtractionFailedError() from e


def _extract_docx(data: bytes) -> str:
    # Every Office file and every plain .zip starts with the same "PK" magic,
    # so the sniff alone cannot tell a DOCX from an XLSX. A real DOCX always
    # carries word/document.xml; anything else is an unsupported type, not a
    # parse failure.
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = archive.namelist()
    except zipfile.BadZipFile as e:
        raise UnsupportedFileError() from e
    if "word/document.xml" not in names:
        raise UnsupportedFileError()

    try:
        doc = Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        raise ExtractionFailedError() from e


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
