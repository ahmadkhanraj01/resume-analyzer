# Resume Analyzer

Upload a resume, paste a job description, and get back a structured report:
a deterministic match score, a per-skill gap analysis, technical and
behavioral interview questions, and a day-by-day preparation plan. Export
any report as a PDF.

**Live app:** not deployed yet. See [Deployment](#deployment) below; the
project is built and tested locally, ready to push to Render, Vercel, and a
managed Postgres instance.

<!-- Add a screenshot of the report view here once deployed:
![Report view](docs/screenshot.png) -->

## Why this exists

Most "AI resume tool" side projects are a thin wrapper around a single LLM
call, including the score itself, which means the same resume can score
differently on every run. This one splits the work on purpose:

- **The match score is deterministic.** It comes from local embeddings
  (`BAAI/bge-small-en-v1.5` via fastembed), cosine similarity between the
  resume and each skill the job description asks for, and a weighted
  aggregate. No network call, no temperature, no drift: the same resume and
  job description always produce the same score.
- **The LLM only generates text that needs generating.** Interview
  questions, the reasoning behind them, and the prep plan. It never grades
  anything, and if it tries to return a score, that value is discarded.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full system design and
[DESIGN.md](DESIGN.md) for the API contract and scoring formula.

## Stack

| Layer      | Choice                                             |
| ---------- | --------------------------------------------------- |
| Backend    | FastAPI, SQLModel, Alembic                          |
| Scoring    | fastembed (ONNX, `bge-small-en-v1.5`), pure Python   |
| LLM        | Groq (primary), Gemini (fallback)                    |
| Database   | Postgres (Supabase or Neon), SQLite for local/tests  |
| PDF export | Jinja2 + WeasyPrint                                  |
| Frontend   | React + Vite, react-router, axios                    |
| Auth       | JWT bearer token (not cookies; see ARCHITECTURE.md)  |

## Project status

Every phase in [PHASES.md](PHASES.md) is implemented and tested locally:

- Backend: 49 tests passing, 2 skipped (PDF rendering needs system libraries
  not present on a bare Windows dev machine; see [Running tests](#running-tests)).
- Frontend: builds cleanly, lints cleanly.
- Not yet done: an actual deploy to Render/Vercel/Supabase, and the real
  20-pair threshold calibration described in `DESIGN.md` (Phase 9) — both
  need accounts and real-world data this environment doesn't have.

## Running it locally

### Prerequisites

- Python 3.12+ (3.13 works; the Docker image targets 3.12)
- Node 20+
- A Groq API key and a Gemini API key (both have free tiers) if you want the
  LLM step to actually produce questions instead of failing over to
  `LLM_UNAVAILABLE`

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate       # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
copy .env.example .env       # then fill in JWT_SECRET, GROQ_API_KEY, GEMINI_API_KEY
uvicorn main:app --reload
```

The API is now at `http://localhost:8000`. With `DATABASE_URL` left at its
SQLite default, tables are created automatically on startup; against a real
Postgres URL, run migrations instead:

```bash
alembic upgrade head
```

The first analysis request downloads the fastembed model (~130 MB) if it
isn't already cached; the Docker image bakes this in at build time so
production never pays that cost.

### Frontend

```bash
cd frontend
npm install
copy .env.example .env.local   # VITE_API_URL, defaults to http://localhost:8000/api
npm run dev
```

The app is now at `http://localhost:5173`.

### Running tests

```bash
cd backend
pytest
ruff check .
ruff format --check .
```

```bash
cd frontend
npm run lint
npm run build
```

PDF export tests are skipped automatically if WeasyPrint's native libraries
(Pango, GDK-Pixbuf, Cairo) aren't installed, which is the normal case on a
bare Windows machine. They run for real in the Docker image, where those
libraries are installed via `apt-get`. To test PDF export locally on
Windows, follow WeasyPrint's
[Windows install steps](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows),
or just build the Docker image.

## Deployment

Not deployed yet. Once you have accounts:

1. **Database:** create a Postgres instance on [Supabase](https://supabase.com)
   or [Neon](https://neon.tech), copy the pooled connection string into
   `DATABASE_URL`.
2. **Backend:** point a Render Docker service at `backend/Dockerfile`. Set
   every key from `backend/.env.example` in Render's dashboard. Run
   `alembic upgrade head` against the production database before the first
   deploy.
3. **Frontend:** point a Vercel project at `frontend/`, with `VITE_API_URL`
   set to the Render backend's URL plus `/api`.

**Cold starts:** Render's free tier sleeps after 15 minutes idle and takes
30 to 50 seconds to wake up. The frontend's staged progress screen accounts
for a slow analysis request, but the very first request after a sleep will
be slower still. An external cron ping every 10 minutes avoids this at the
cost of the instance never really sleeping.

## Known limitations

- **No refresh tokens, password reset, or email verification.** Sessions
  last 24 hours; expiry just logs you out. See ARCHITECTURE.md for why.
- **Scoring thresholds are starting values**, not calibrated against real
  resume/JD pairs yet (`DESIGN.md`'s Phase 9 task). A literal mention of a
  skill in the resume is always treated as covered regardless of threshold,
  which fixes the obvious case; everything in between is a reasonable guess
  until real data says otherwise.
- **Rate limiting is in-process**, correct for a single Render instance,
  wrong the moment a second worker exists (see `app/core/limiter.py`).
- **No job scraping, multi-resume comparison, or resume rewriting.** Out of
  scope for v1; see `DESIGN.md`.

## Repository layout

See [STRUCTURE.md](STRUCTURE.md) for the full file-by-file layout and the
rules for each directory.

## License

Personal / portfolio project. No license file yet; ask before reusing.
