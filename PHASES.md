# Build phases

Ten phases, 0 through 9. Each ends with something you can run and verify. Do
not start a phase before its checkpoint above it passes.

Status: `[ ]` not started, `[~]` in progress, `[x]` done.

---

## Phase 0: skeleton and deploy [~]

Deploy an empty app before writing features. Doing this last means debugging
deployment and business logic simultaneously, which is where most side projects
stall.

- `backend/` with `main.py`, a `/api/health` route returning `{"ok": true}`
- `requirements.txt`, `.gitignore`, `.env.example`
- `Dockerfile` for the backend
- `frontend/` scaffolded with Vite, default page untouched
- Git repo, initial commit, pushed
- Render service pointed at the Dockerfile
- Vercel project pointed at `frontend/`

**Checkpoint:** `curl https://your-app.onrender.com/api/health` returns
`{"ok":true}` from a public URL, and the Vercel URL loads the default Vite page.

**Time:** half a day, most of it fighting Render.

**Status:** everything that doesn't need an external account is done: the
backend, Dockerfile, and frontend all run locally (`curl localhost:8000/api/health`
returns `{"ok":true}`, `npm run dev` serves the app). Not done: the actual
Render service and Vercel project (need real accounts), and the commit/push
(RULES.md: the human runs the commit, the push, and the merge, not an agent).

---

## Phase 1: config, database, models [~]

- `app/core/config.py` with pydantic-settings, all values from env
- Supabase or Neon project created, pooled connection string in env
- `app/db/session.py`, engine plus session dependency
- `app/db/models.py`: `User` and `Report` per `ARCHITECTURE.md`
- Alembic initialized, first migration applied

**Checkpoint:** tables exist in the hosted database, visible in the Supabase
table editor. Health endpoint still works with the DB dependency injected.

**Status:** config, models, and the first Alembic migration are done and
verified against a local SQLite database (`alembic upgrade head` /
`alembic downgrade base` both run clean). Not done: an actual Supabase or
Neon project, so the migration has never run against real Postgres. The
model's JSON columns use `JSONB().with_variant(JSON(), "sqlite")` so the
same migration is correct for both.

---

## Phase 2: authentication [x]

- `app/core/security.py`: bcrypt hashing, JWT encode and decode
- `app/core/deps.py`: `get_current_user` reading the bearer header
- `app/api/auth.py`: register, login, me
- Central exception handler producing the error shape from `DESIGN.md`

**Checkpoint:**

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"a@b.com","password":"testpass123"}' | jq -r .access_token)

curl localhost:8000/api/auth/me -H "Authorization: Bearer $TOKEN"
```

Second register with the same email returns a clean 422, not a raw integrity
error. A garbage token returns `TOKEN_INVALID`.

**Status:** done, checkpoint run exactly as written (register, curl `/me`
with the token, duplicate register returns 422, garbage token returns
`TOKEN_INVALID`). 10 tests in `tests/test_auth.py`.

---

## Phase 3: file extraction [x]

- `app/services/extract.py`: `to_text(data: bytes, filename: str) -> str`
- `pypdf` for PDF, `python-docx` for DOCX
- Magic byte validation, not extension trust
- Raise `ExtractionError` when output is under 100 characters, which means a
  scanned image

**Checkpoint:** a script that feeds three real resumes, one PDF, one DOCX, one
scanned PDF, and prints the result. The scanned one raises. Read the extracted
text yourself before moving on; garbage in here poisons every later phase.

**Status:** done. The three fixtures are synthetic (a hand-built PDF and a
python-docx DOCX with the same resume text, plus a text-free PDF standing in
for a scan) rather than real resumes, since none were available in this
environment; extracted text was read and confirmed correct before Phase 4
started. 5 tests in `tests/test_extract.py`.

---

## Phase 4: scoring [x]

The differentiating phase. Take the time.

- `app/services/scoring.py`
- fastembed with `BAAI/bge-small-en-v1.5`, model loaded once at module level
- Chunking, 200 tokens with 50 token overlap
- Skill extraction, regex seed list first, LLM pass added in Phase 5
- Cosine similarity, max per skill, thresholds from config
- Weighted aggregate per the formula in `DESIGN.md`
- Unit tests with fixture pairs, asserting exact scores

**Checkpoint:** a CLI script scores a resume against a JD and prints the score
plus the per-skill breakdown, with no server and no LLM. Run it twice; the
numbers are identical. Then hand-check five skills. If "Docker" is marked
missing on a resume that says Docker, fix the chunking before continuing.

**Also:** measure peak memory here. If it exceeds 400 MB, Phase 0's deployment
will OOM later and it is cheaper to find out now.

**Status:** done, and the exact failure this checkpoint warns about did show
up: a resume that says "Docker" was scoring it as partial (0.62 similarity),
not covered, because a two-word skill embedded against a 200-word chunk
structurally caps well below 0.75 even for an exact match. Fixed with a
literal-mention floor in `scoring.py` rather than a chunking change; see the
comment on `_literal_mention`. Peak RSS measured at ~279 MB (~116 MB
interpreter/import baseline + the model), under the 400 MB ceiling. Skill
extraction (regex + LLM union) landed in its own `services/skills.py` per
STRUCTURE.md rather than inside `scoring.py`, and was built together with
its Phase 5 LLM pass rather than staged across two phases. 17 tests across
`tests/test_scoring.py` and `tests/test_skills.py`, exact-value assertions
throughout.

---

## Phase 5: LLM service [~]

- `app/schemas/report.py`, the full contract with all list bounds
- `app/services/llm.py`: one `generate_report` function
- Groq primary, Gemini fallback
- Prompt assembled per `DESIGN.md`, scoring output included as authoritative
- Fence stripping, `model_validate_json`, one retry with the validation error
- Discard any score the model returns
- Add the LLM skill-extraction pass to `scoring.py` and union it with the regex
  pass

**Checkpoint:** a standalone script calls `generate_report` with hardcoded text
and prints a validated `InterviewReport`. Force a failure by pointing the
primary at a bad key and confirm the fallback fires. Feed it a deliberately
malformed mock response and confirm the retry path runs.

**Status:** code is done and every path in the checkpoint is proven, but
with mocked providers rather than real ones: no Groq or Gemini API key was
available in this environment. Confirmed instead by pointing the real app at
fake keys through the full HTTP stack and getting a correctly-shaped
`LLM_UNAVAILABLE` after both providers genuinely failed (real network
calls, real auth errors), plus 7 mocked tests in `tests/test_llm.py`
covering fence-stripping, the discarded score, the one-retry
self-correction path, and the Groq-to-Gemini fallback. Before wiring in real
keys, run `python -c "from app.services.llm import generate_report; ..."`
with hardcoded text to see real output.

---

## Phase 6: interview endpoints [~]

- `app/api/interview.py`: create, list, detail, delete
- Multipart handling with size and type limits
- `run_in_threadpool` around extraction and scoring
- Persist the full report including `resume_text`
- Every query filtered by `user_id`, foreign ids return 404
- In-process rate limiter behind one swappable interface

**Checkpoint:** full flow through curl with a real file and a real token.
Register a second user, grab the first user's report id, confirm 404. Deploy and
run the same flow against the public URL.

**Status:** done locally, including the cross-user 404 check, both through
`pytest` (10 tests in `tests/test_interview.py`) and a live curl run against
a real running server (real extraction, real scoring, real skill
extraction; LLM mocked in pytest, genuinely attempted and gracefully
rejected in the live run since no real provider keys exist here). Added
`services/analysis.py` to orchestrate extract → skills → score → LLM as one
unit, and reports beyond the 50-per-user cap are pruned on every create
(pulled forward from Phase 9's list, since it's naturally part of this
endpoint). Not done: running the same flow against a public URL, since
nothing is deployed yet.

---

## Phase 7: frontend [~]

- `src/api/client.js`, the single axios instance with request and response
  interceptors
- `AuthContext` with a loading state, hydrated by `/auth/me`
- `ProtectedRoute` that waits for loading before redirecting
- Pages: Login, Register, New Analysis, History, Report Detail
- Upload form with `FormData`, and do not set `Content-Type` manually
- Staged progress messages during analysis, per `DESIGN.md`
- Per-code error messages, especially `EXTRACTION_FAILED`
- Report view: score, gaps sorted by severity, questions with collapsed answers,
  then the plan

**Checkpoint:** the deployed Vercel frontend completes a full analysis against
the deployed backend. Test in a private window with a fresh account. Refresh on
a protected route and confirm no login flash.

**Status:** builds and lints clean (`npm run build`, `npm run lint`). Ran
locally against the real local backend in the browser: register, redirect
to `/new`, refresh on `/reports` with no login flash (waits for `/auth/me`
before deciding), and a 401 from an invalidated token correctly logs the
user out via the response interceptor. ESLint is `eslint.config.js`, not
the `.eslintrc.cjs` STRUCTURE.md names, because ESLint 10 dropped support
for the legacy config format. Not done: an actual upload through the
browser's file picker (this environment's browser automation can't attach
a file) and the deployed-Vercel-against-deployed-Render checkpoint, since
neither is deployed. The upload path itself is proven by the Phase 6 curl
run and the `pytest` integration tests, which exercise the same endpoint.

---

## Phase 8: PDF export [~]

- `app/services/pdf.py`, Jinja2 template plus a print stylesheet
- WeasyPrint, `StreamingResponse`, nothing written to disk
- `POST /interview/{id}/pdf`, ownership checked
- Download button on the report page

**Checkpoint:** the generated PDF opens correctly, paginates without cutting
text mid-line, and downloads from the deployed frontend. Verify WeasyPrint's
system dependencies are in the Dockerfile; this is the most common deploy break
in the whole build.

**Status:** code is done (Jinja2 template, print stylesheet, `StreamingResponse`,
ownership check, download button) but unverified against a real render:
WeasyPrint needs Pango/GDK-Pixbuf/Cairo, which this Windows dev machine
doesn't have, so `render_report_pdf` is imported lazily and its tests
(`tests/test_pdf.py`) skip rather than fail when those libraries are
missing. The Dockerfile installs them via `apt-get`, matching WeasyPrint's
own documented Debian dependency list, but that install has not been run:
no Docker is available in this environment either. This is exactly the
"most common deploy break" the checkpoint warns about. Treat the first
Render deploy as the real test of this phase, not this local run.

---

## Phase 9: polish [~]

- README with a screenshot, a live link, and a note about the cold start
- Threshold calibration against twenty real resume and JD pairs, committed as a
  fixture set
- Structured logging with a request id
- Prune reports beyond 50 per user
- Optional: cron ping to keep the instance warm

**Checkpoint:** hand the link to someone who has never seen it and watch them
use it without instructions.

**Status:** README with setup instructions and a cold-start note is done (no
live link or screenshot yet, since nothing is deployed). Report pruning
beyond 50 per user landed in Phase 6 instead. Not done: real threshold
calibration against twenty resume/JD pairs (no real resumes available here;
`docs/calibration/` is still empty), structured logging with a request id,
and the optional cron ping.

---

## Phase 10: career fit [x]

- Curated role profiles in `backend/app/data/role_profiles.json`, drafted by
  the LLM once and reviewed by hand, with an alias map for spellings
- `services/careers.py` ranks a resume against every profile with one
  embedding pass and cached skill embeddings; no LLM call, nothing stored
- `POST /interview/careers` and a Career fit panel on the new-analysis page
  that lists the top five roles and fills the target role on click

**Checkpoint:** a Flutter intern's resume ranks Flutter Developer first, an
ML-heavy resume ranks AI Engineer first, and neither ranks Accountant in the
top five.

**Status:** done. Came out of running the three resumes in `Sample/` against
a dozen typed role targets: the LLM-inferred profile for the same role
changed from one request to the next, so the scores drifted. Checked-in
profiles fix the drift and make ranking cheap enough to run on upload.

---

## Deferred

Not in this build. Listed so they stay out of scope rather than creeping in.

- TypeScript across the frontend
- Refresh tokens, password reset, email verification
- Resume rewriting and generation
- Comparing one resume against several JDs
- pgvector and a stored job posting corpus
- Background job queue
- Docker Compose for local development
- CI pipeline

---

## Order rationale

Deployment is first because it is the phase most likely to reveal a blocker,
memory limits, build failures, missing system libraries, and the cheapest time
to discover that is when there is nothing to lose.

Scoring comes before the LLM because it is the part that is genuinely yours. If
the LLM layer gets built first, the temptation is to let it produce the score
too, and the project becomes another API wrapper.

The frontend comes late because a working API can be exercised entirely with
curl, and building UI against an unstable contract means building it twice.
