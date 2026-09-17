# Tests

Run with `pytest` from `backend/`. Every test uses a fresh in-memory SQLite
database and a mocked LLM; nothing here reaches the network.

| File               | Covers                                                     |
| ------------------ | ---------------------------------------------------------- |
| test_auth.py       | register, login, token handling, password byte limit, throttling |
| test_extract.py    | PDF and DOCX extraction, scanned, corrupted, and disguised files |
| test_skills.py     | seed matching, single-letter seeds, JD hash cache          |
| test_scoring.py    | exact-value assertions on the deterministic scorer         |
| test_llm.py        | provider chain, fence stripping, retry on malformed JSON   |
| test_analysis.py   | the LLM never sets skill gap numbers                       |
| test_limiter.py    | acquire and release semantics                              |
| test_pdf.py        | WeasyPrint rendering; skipped without native libraries     |
| test_interview.py  | full create, list, get, delete flow through TestClient     |
| test_contracts.py  | error codes agree across DESIGN.md, backend, and frontend  |

`fixtures/` holds a synthetic resume in PDF and DOCX form, a scanned PDF with
no text layer, and a sample job description.
