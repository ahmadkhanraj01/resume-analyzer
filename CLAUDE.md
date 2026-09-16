# CLAUDE.md

Instructions for AI coding agents working in this repository.

## What this is

A resume and interview analyzer. FastAPI backend, React frontend, Postgres.
Deterministic embedding-based skill scoring plus an LLM for generated content.

Read `ARCHITECTURE.md` for structure and `DESIGN.md` for contracts before
changing anything non-trivial. `PHASES.md` tracks build order and current state.

## Layout

```
backend/           FastAPI. Source of truth for all business logic.
  app/core/        config, security, dependencies
  app/db/          SQLModel models and session
  app/schemas/     Pydantic contracts
  app/services/    extract, scoring, llm, pdf. No FastAPI imports here.
  app/api/         routers. Thin.
frontend/          React + Vite
  src/api/         the single axios instance
  src/context/     AuthContext
  src/pages/
  src/components/
```

## Commands

```bash
# backend
cd backend
uvicorn main:app --reload           # dev server on :8000
pytest                              # tests
ruff check . && ruff format .       # lint and format

# frontend
cd frontend
npm run dev                         # dev server on :5173
npm run build
npm run lint
```

## Rules

**Services stay framework-free.** Nothing in `app/services/` imports FastAPI,
touches `Request`, or raises `HTTPException`. Services raise domain exceptions;
routers translate them. This is what makes the scoring logic testable without a
server and is the most common rule to accidentally break.

**Routers stay thin.** Validate, call a service or two, persist, return. If a
router body exceeds roughly 20 lines, logic belongs in a service.

**The Pydantic report model is the contract.** `app/schemas/report.py` is
mirrored by the DB columns, the LLM prompt, and the frontend. Changing it means
changing all four in the same commit, plus a migration.

**The LLM never produces the match score.** Scoring is deterministic and lives
in `services/scoring.py`. If a model returns a score field, discard it. Do not
"improve" this by asking the model to grade.

**Never trust an id from the path.** Every report query filters by the
authenticated `user_id`. A missing or foreign id returns 404, never 403.

**No secrets in code.** Read through `app/core/config.py` only. Do not add a
fallback default for an API key.

**Async correctly.** Route handlers are `async def`. Blocking work, which means
fastembed, WeasyPrint, and PDF text extraction, goes through
`run_in_threadpool`. Putting a synchronous embedding call directly in an async
handler blocks the entire event loop and is easy to miss in local testing with
one user.

**Ephemeral filesystem.** Render's disk does not persist. Never write uploads,
generated PDFs, or caches to disk expecting them to survive. Everything is in
memory or in Postgres.

## Writing style for docs and comments

- No em dashes.
- Concise and specific. Cut filler openers.
- Comments explain why, not what. `# retry once with the validation error so the
  model can self-correct` is useful; `# retry` is not.

## Testing

- `services/scoring.py` gets real unit tests with fixture resumes and JDs. It is
  deterministic, so assertions on exact scores are valid and should be used.
- `services/llm.py` is tested with mocked provider responses, including a
  malformed one to prove the retry path works.
- Routers get integration tests through `TestClient` against a test database.
- Do not write tests that hit a live LLM API.

## Before proposing a change

- Check `PHASES.md`. Work belonging to a later phase should not be pulled
  forward without saying so.
- Prefer editing an existing module to adding a new one.
- Do not add a dependency without stating what it replaces and why the stdlib or
  an existing dependency is insufficient. The deployment target has 512 MB of
  memory and the image already carries an ONNX model.
- Do not introduce Redis, Celery, a vector database, or a second service.
  `ARCHITECTURE.md` explains why each was excluded. If one becomes genuinely
  necessary, say so and wait rather than adding it silently.

## Known constraints

- Free Render instance: 512 MB memory, sleeps after 15 minutes idle, 30 to 50
  second cold start.
- fastembed model is baked into the Docker image. Do not move it to a runtime
  download.
- Auth is a bearer token in a header, not a cookie, because the frontend and
  backend are on different domains. Do not switch to cookies without also
  solving the cross-site problem.
- Analysis is synchronous and takes 8 to 25 seconds. The frontend accounts for
  this with staged progress. Do not replace it with a bare spinner.
