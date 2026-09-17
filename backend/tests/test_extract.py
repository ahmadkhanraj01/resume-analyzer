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


def test_corrupted_pdf_raises_extraction_failed():
    # Valid header, garbage body: passes the sniff, fails inside pypdf.
    data = b"%PDF-1.7\n" + b"\x00garbage" * 200
    with pytest.raises(ExtractionFailedError):
        extract.to_text(data)


def test_plain_zip_raises_unsupported():
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("hello.txt", "not a resume")
    with pytest.raises(UnsupportedFileError):
        extract.to_text(buf.getvalue())


def test_xlsx_shaped_zip_raises_unsupported():
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", "<Types/>")
        z.writestr("xl/workbook.xml", "<workbook/>")
    with pytest.raises(UnsupportedFileError):
        extract.to_text(buf.getvalue())


def test_truncated_docx_raises_extraction_failed():
    data = (FIXTURES / "resume_sample.docx").read_bytes()
    # Keep the zip header so it still sniffs as DOCX, then cut it off.
    with pytest.raises((ExtractionFailedError, UnsupportedFileError)):
        extract.to_text(data[: len(data) // 2])
