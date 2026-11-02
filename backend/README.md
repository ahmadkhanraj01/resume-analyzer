# Backend

FastAPI service. Source of truth for all business logic: extraction,
deterministic skill scoring, LLM report generation, PDF export, auth.

## Layout

```
main.py            app factory, CORS, exception handlers, lifespan
app/__init__.py    on Vercel, points model caches at /tmp (the only writable path)
app/core/          config (env only), security, deps, limiter, exceptions
app/db/            SQLModel tables, session, Postgres-backed rate limits and skill-list cache
app/schemas/       Pydantic contracts; report.py is the master contract
app/services/      extract, skills, scoring, llm, analysis, careers, pdf. No FastAPI here.
app/api/           thin routers
app/data/          skill seed list, curated role profiles with aliases
app/templates/     Jinja2 + CSS for the PDF
migrations/        Alembic
tests/             pytest, see tests/README.md
ruff.toml          lint config
pytest.ini         test config
vercel.json        Vercel function settings (300 s max, tests left out of the bundle)
Dockerfile         image for Render or any Docker host
```

There is deliberately no `pyproject.toml`: Vercel reads one as the
dependency list and then ignores `requirements.txt`.

## Run locally

Needs Python 3.12 or newer.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # fill in JWT_SECRET (32+ bytes) and provider keys
uvicorn main:app --reload          # http://localhost:8000/api/health
```

With the default `DATABASE_URL` the app uses a local SQLite file (`dev.db`),
creates tables on startup, and adds columns new models gained. Rate limits
are kept in memory there.

Against Postgres, apply migrations first. Alembic uses `DATABASE_URL_UNPOOLED`
when it is set and falls back to `DATABASE_URL`; on Neon, give it the direct
connection string, because migrations should not run through the pooler:

```bash
DATABASE_URL_UNPOOLED=<direct connection string> alembic upgrade head
```

## Environment

| Variable | Required | Notes |
| --- | --- | --- |
| `JWT_SECRET` | yes | 32+ bytes; the app refuses to start without it. `openssl rand -hex 32` |
| `DATABASE_URL` | production | Neon **pooled** URL. Unset means SQLite `dev.db` |
| `DATABASE_URL_UNPOOLED` | migrations | Neon **direct** URL, used only by Alembic |
| `GROQ_API_KEY`, `GEMINI_API_KEY` | for reports | Without them, analysis fails with `LLM_UNAVAILABLE` |
| `GROQ_MODEL`, `GEMINI_MODEL` | no | Defaults `openai/gpt-oss-120b`, `gemini-3.6-flash` |
| `CORS_ORIGINS` | production | Comma-separated frontend origins, no wildcard |
| `ANALYSES_PER_HOUR`, `ANALYSES_PER_DAY`, `AUTH_ATTEMPTS_PER_HOUR`, `MAX_REPORTS_PER_USER` | no | Defaults 10, 30, 20, 50 |
| `VERCEL` | no | Set by Vercel itself; switches the model cache to `/tmp` and trusts `x-real-ip` for login throttling |

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

## Deploying on Vercel (what runs live)

Import the repository as a Vercel project with root directory `backend`.
Vercel detects FastAPI (`app` in `main.py`), installs `requirements.txt`, and
needs no build or output settings. Set the production variables from the
table above. Then:

- **Migrations are manual.** There is no container start to run them from:
  run `alembic upgrade head` against the direct URL before deploying code
  that adds one. If `rate_hits` is missing, rate limits fail open and log
  `rate limit check failed`.
- **No PDF engine.** WeasyPrint's native libraries are not on Vercel's
  runtime; `POST /interview/{id}/pdf` answers 503 `PDF_UNAVAILABLE`, and the
  frontend falls back to browser print.
- **Cold starts** download the model to `/tmp` (about 65 MB), a few seconds.
- **Logs:** `vercel logs -p <project>` with the Vercel CLI, or the project's
  Logs tab.

## Docker

```bash
docker build -t resume-analyzer-backend .
docker run -p 8000:8000 --env-file .env resume-analyzer-backend
```

The image bakes the fastembed model and WeasyPrint's native libraries, runs
as a non-root user, and exposes a healthcheck on `/api/health`. On start it
runs `alembic upgrade head`, then serves on `$PORT` (default 8000), which
is what Render's free tier needs; `../render.yaml` describes that deploy.

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
- Anything kept between requests must live in Postgres, not process
  memory: on Vercel each request may hit a different short-lived copy of
  the app. Rate limits (`rate_hits`) and LLM skill lists (`skill_lists`)
  already do (on SQLite, the rate limiter uses an in-memory version).
- A new error code needs a line in `DESIGN.md` and in the frontend's
  `src/lib/errorMessages.js`; `tests/test_contracts.py` fails otherwise.
- Every report query filters by the authenticated user and returns 404, not
  403, for a foreign id.
