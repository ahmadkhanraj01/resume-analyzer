from pathlib import Path

import pytest

from app.core.exceptions import ExtractionFailedError, UnsupportedFileError
from app.services import extract

FIXTURES = Path(__file__).parent / "fixtures"


def test_extracts_text_from_pdf():
    data = (FIXTURES / "resume_sample.pdf").read_bytes()
    text = extract.to_text(data)
    assert "Jordan Rivera" in text
    assert "FastAPI" in text


def test_extracts_text_from_docx():
    data = (FIXTURES / "resume_sample.docx").read_bytes()
    text = extract.to_text(data)
    assert "Jordan Rivera" in text
    assert "PostgreSQL" in text


def test_scanned_pdf_raises_extraction_failed():
    data = (FIXTURES / "resume_scanned.pdf").read_bytes()
    with pytest.raises(ExtractionFailedError):
        extract.to_text(data)


def test_unknown_file_type_raises_unsupported():
    with pytest.raises(UnsupportedFileError):
        extract.to_text(b"just some random bytes, not a pdf or docx")


def test_empty_bytes_raises_unsupported():
    with pytest.raises(UnsupportedFileError):
        extract.to_text(b"")
