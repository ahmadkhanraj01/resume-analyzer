# Tests

Run with `pytest` from `backend/`. Every test uses a fresh in-memory SQLite
database, and `conftest.py` blocks both LLM provider functions and resets the
in-process rate limiters for every test; nothing here reaches the network and
no test depends on how many analyses ran before it.

| File               | Covers                                                     |
| ------------------ | ---------------------------------------------------------- |
| test_auth.py       | register, login, token handling, password byte limit, throttling |
| test_extract.py    | PDF and DOCX extraction, scanned, corrupted, and disguised files |
| test_skills.py     | seed matching, single-letter seeds, JD hash cache          |
| test_scoring.py    | exact-value assertions on the deterministic scorer, credit curve, literal and alias matching |
| test_careers.py    | role profile file shape, career ranking, batch scoring equals single scoring |
| test_llm.py        | provider chain, fence stripping, retry on malformed JSON   |
| test_analysis.py   | the LLM never sets skill gap numbers                       |
| test_limiter.py    | acquire and release semantics                              |
| test_pdf.py        | WeasyPrint rendering; skipped without native libraries     |
| test_interview.py  | full create, list, get, delete flow, role-profile routing, career-fit endpoint agrees with the report |
| test_contracts.py  | error codes agree across DESIGN.md, backend, and frontend  |

`fixtures/` holds a synthetic resume in PDF and DOCX form, a scanned PDF with
no text layer, and a sample job description.
