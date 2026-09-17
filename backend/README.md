# Backend

FastAPI service. Source of truth for all business logic: extraction,
deterministic skill scoring, LLM report generation, PDF export, auth.

## Layout

```
main.py            app factory, CORS, exception handlers, lifespan
app/core/          config (env only), security, deps, limiter, exceptions
app/db/            SQLModel tables and session
app/schemas/       Pydantic contracts; report.py is the master contract
app/services/      extract, skills, scoring, llm, analysis, careers, pdf. No FastAPI here.
app/api/           thin routers
app/data/          skill seed list, curated role profiles with aliases
app/templates/     Jinja2 + CSS for the PDF
migrations/        Alembic
tests/             pytest, see tests/README.md
```

## Run locally

Needs Python 3.12 or newer.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # fill in JWT_SECRET (32+ bytes) and provider keys
uvicorn main:app --reload          # http://localhost:8000/api/health
```

With the default `DATABASE_URL` the app uses a local SQLite file and creates
tables on startup. Against Postgres, run `alembic upgrade head` first.

## Test and lint

```bash
pytest
ruff check . && ruff format .
```

Tests never call a live LLM: `tests/conftest.py` blocks both provider
functions for every test, so a `.env` with real keys changes nothing. PDF
tests skip themselves when WeasyPrint's native libraries are missing, which
is normal on Windows.

## Smoke testing with real resumes

`../Sample/` holds untracked personal resumes. Two scripts worth keeping in
mind when scoring changes:

- Score a resume against a typed role without generating a report:
  `careers.rank_careers(extract.to_text(data))` from a `PYTHONPATH=.`
  shell. Deterministic, no network.
- Run the whole pipeline including the LLM report: call
  `analysis.run_analysis(data, "I want to be an AI Engineer.", "", settings)`.
  The report's `match_score` must equal the career-fit score for the same
  role; `tests/test_interview.py` asserts this on the fixture resume.

## Docker

```bash
docker build -t resume-analyzer-backend .
docker run -p 8000:8000 --env-file .env resume-analyzer-backend
```

The image bakes the fastembed model, runs as a non-root user, and exposes a
healthcheck on `/api/health`.

## Rules that are easy to break

- Services never import FastAPI. They raise domain exceptions from
  `app/core/exceptions.py`; the handlers in `main.py` translate them.
- The LLM never produces the match score or the skill gap numbers. Those
  come from `services/scoring.py` only.
- Role profiles the app knows live in `app/data/role_profiles.json`. When a
  typed target names one, the analysis uses it and skips the LLM profile
  call. The LLM writes a profile only for roles the file does not cover.
- Blocking work (embeddings, PDF rendering, extraction) goes through
  `run_in_threadpool`.
- Every report query filters by the authenticated user and returns 404, not
  403, for a foreign id.
