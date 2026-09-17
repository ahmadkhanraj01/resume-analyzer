"""Every error code in DESIGN.md must exist in both core/exceptions.py and
the frontend's errorMessages.js, so the three cannot drift."""

import inspect
import re
from pathlib import Path

from app.core import exceptions

ROOT = Path(__file__).parent.parent.parent


def _design_codes() -> set[str]:
    text = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    return set(re.findall(r"^\| `([A-Z_]+)`\s+\| \d{3}", text, re.MULTILINE))


def _backend_codes() -> set[str]:
    return {
        cls.code
        for _, cls in inspect.getmembers(exceptions, inspect.isclass)
        if issubclass(cls, exceptions.DomainError) and cls is not exceptions.DomainError
    }


def _frontend_codes() -> set[str]:
    text = (ROOT / "frontend" / "src" / "lib" / "errorMessages.js").read_text(encoding="utf-8")
    return set(re.findall(r"^\s+([A-Z_]+):", text, re.MULTILINE))


def test_error_codes_match_across_design_backend_and_frontend():
    design = _design_codes()
    assert design, "no codes parsed from DESIGN.md"
    assert design == _backend_codes()
    assert design == _frontend_codes()
