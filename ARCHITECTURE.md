# Architecture

## Overview

A full-stack resume and interview analyzer. A user uploads a resume, pastes a
job description and a short self description, and receives a structured report:
a deterministic match score, per-skill gap analysis, generated interview
questions, and a preparation plan. Reports can be exported as PDF.

The system deliberately splits two kinds of work:

- **Deterministic scoring**, done locally with embeddings. Reproducible, free,
  fast, and defensible when someone asks "where did 72% come from?"
- **Generative reasoning**, done by an LLM. Used only for text that genuinely
  requires generation: questions, explanations, plans.

This split is the core design decision. Everything else follows from it.

---

## System diagram

An editable version is in `docs/architecture.drawio` (open with
[app.diagrams.net](https://app.diagrams.net) or the VS Code draw.io
extension).

```
                 ┌──────────────────────────┐
                 │   React + Vite (Vercel)  │
                 │   axios + Bearer token   │
                 └───────────┬──────────────┘
                             │  HTTPS / JSON
                             ▼
                 ┌──────────────────────────┐
                 │   FastAPI (Vercel)       │
                 │                          │
                 │   api/      auth,        │
                 │             interview    │
                 │   services/ extract      │
                 │             scoring      │
                 │             careers      │
                 │             llm          │
                 │             pdf          │
                 └───┬──────────┬───────┬───┘
                     │          │       │
        ┌────────────┘          │       └──────────────┐
        ▼                       ▼                      ▼
┌───────────────┐   ┌───────────────────┐   ┌──────────────────┐
│  Postgres     │   │  fastembed        │   │  Groq / Gemini   │
│  (Supabase)   │   │  (local ONNX)     │   │  (HTTP)          │
│  users        │   │  bge-small-en     │   │  JSON-only       │
│  reports      │   │  cosine sim       │   │  Pydantic-valid  │
└───────────────┘   └───────────────────┘   └──────────────────┘
```

---

## Components

### Frontend (React + Vite)

Thin client. Holds no business logic beyond form validation and rendering.

- `api/client.js` is the only place axios is configured. A request interceptor
  attaches the bearer token; a response interceptor catches 401 and clears auth
  state.
- `AuthContext` holds the current user, hydrated by `GET /api/auth/me` on mount.
  Routes render a loading state until that resolves, otherwise protected routes
  flash the login page on every refresh.
- Pages: Register, Login, New Analysis, Report Detail, History.
- New Analysis scores the resume against the curated role profiles as soon
  as it is uploaded and offers each suggested role as a button that fills the
  target box.
- Report Detail shows the score as a measuring tape, then skill gaps, resume
  edits, questions, and the plan, with a sticky section rail on desktop.

### Backend (FastAPI)

```
backend/
  main.py                  app factory, CORS, router mounting
  app/
    core/
      config.py            pydantic-settings, reads env
      security.py          hashing, JWT encode/decode
      deps.py              get_db, get_current_user
    db/
      session.py           engine, session factory
      models.py            SQLModel tables
    schemas/
      auth.py              register/login/token payloads
      report.py            the report contract (shared with the LLM)
    services/
      extract.py           PDF/DOCX -> plain text
      scoring.py           embeddings -> match score, skill gaps
      llm.py               provider fallback, JSON validation, retry
      pdf.py               Jinja2 + WeasyPrint
    api/
      auth.py
      interview.py
```

Routers stay thin. They validate input, call one or two services, persist, and
return. All real logic lives in `services/`, which import nothing from FastAPI
and can be run from a plain script or a test.

### Database (Postgres)

Two tables. Managed Postgres on Supabase or Neon; both have a usable free tier
and speak plain `postgresql://`, so nothing in the code is vendor-specific.

```
users
  id            uuid pk
  email         text unique not null
  password_hash text not null
  created_at    timestamptz

reports
  id                uuid pk
  user_id           uuid fk -> users.id  (indexed)
  title             text
  job_description   text
  self_description  text
  resume_text       text        -- extracted, stored for regeneration
  match_score       int         -- 0..100, from scoring.py
  scored_against    text        -- job_description or role_profile
  role_title        text null   -- set when scored against a role profile
  resume_filename   text null   -- uploaded file's base name, display only
  skill_gaps        jsonb
  technical_qs      jsonb
  behavioral_qs     jsonb
  preparation_plan  jsonb
  resume_keywords   jsonb       -- JD terms missing from the resume
  resume_rewrites   jsonb       -- {original, improved, reason} per weak line
  created_at        timestamptz
```

skill_lists
  key               text pk     -- "jd:" or "role:" + sha256 of folded text
  role              text null   -- set for an inferred role profile
  skills            jsonb       -- the LLM's first answer, reused forever
  created_at        timestamptz

`skill_lists` is what makes a pasted posting score the same every time: see
"Skill extraction" in DESIGN.md.

JSONB rather than child tables. The nested structures are read as whole
documents and never queried by their inner fields, so normalizing them buys
joins and nothing else. If a "search all reports by skill" feature ever lands,
a GIN index on `skill_gaps` covers it.

`resume_text` is stored deliberately. It lets a user regenerate or re-score a
report without re-uploading the file, and the raw file is never persisted.

### Scoring service

The piece that distinguishes this from a thin LLM wrapper.

1. Pull a candidate skill list from the job description.
2. Embed each JD skill and each resume chunk with `BAAI/bge-small-en-v1.5`
   through fastembed. ONNX runtime, no torch, roughly 130 MB resident.
3. For each JD skill, take the max cosine similarity against resume chunks.
4. Classify: above 0.75 covered, 0.62 to 0.75 partial, below 0.62 missing.
5. Aggregate into a 0 to 100 score, weighting skills the JD repeats.

No network call, no temperature, no drift. The same inputs always produce the
same score, which is the whole point.

Thresholds live in `config.py`, not scattered through the module, because they
will need tuning against real resumes.

The same scorer backs the career-fit endpoint through `services/careers.py`:
the resume is embedded once and scored against every profile in
`data/role_profiles.json`, whose skill embeddings are cached per list. That
keeps a 36-role ranking to about one embedding pass and no LLM call.

### LLM service

Called after scoring, and given the scoring output as context so the questions
and prep plan target the actual gaps.

- Provider chain: Groq first for latency, Gemini as fallback on error or rate
  limit. One interface, `generate_report(...) -> InterviewReport`.
- The Pydantic model is the contract. The prompt embeds the JSON schema, the
  response is parsed with `model_validate_json`, and a validation error triggers
  exactly one retry with the error text appended.
- Markdown fences are stripped defensively before parsing regardless of what the
  prompt asked for.
- The LLM never produces the match score. If it returns one, it is discarded.
- The same call suggests resume edits: keywords from the job description and
  rewrites of weak resume lines. `analysis.py` drops any keyword the resume
  already contains and any rewrite whose original line is not actually on the
  resume, so the model cannot ask the user to change text they never wrote.

### PDF service

Jinja2 template plus a print stylesheet, rendered by WeasyPrint. Chosen over
Puppeteer because it is pure Python, adds no Chromium download to the image, and
does not need a headless browser process on a 512 MB instance. Returns a
`StreamingResponse` with `application/pdf`; nothing touches disk.

---

## Request flow: analysis

```
POST /api/interview/  (multipart: resume file + jd + self_description)
  │
  ├─ deps.get_current_user      decode bearer token, load user
  ├─ extract.to_text(file)      pypdf or python-docx, in memory
  ├─ pick the rubric
  │     ├─ short text naming a curated role  -> role_profiles.json, no LLM
  │     ├─ otherwise skills.extract_skills   -> regex seeds + LLM pass
  │     └─ nothing found                     -> llm.infer_role_profile
  ├─ scoring.score(text, skills, aliases)   embeddings, deterministic
  ├─ llm.generate_report(text, jd, scoring_result)
  │     └─ Groq -> validate -> (retry once) -> fallback Gemini
  ├─ persist Report
  └─ 201 { report }
```

Total latency is dominated by the LLM call, typically 8 to 25 seconds. The
frontend must show progress, not a spinner that looks frozen.

## Request flow: career fit

```
POST /api/interview/careers  (multipart: resume file only)
  │
  ├─ deps.get_current_user
  ├─ extract.to_text(file)
  ├─ careers.rank_careers(text)
  │     └─ scoring.score_profiles: embed the resume once, cached skill
  │        embeddings per profile, every profile scored and sorted
  └─ 200 { fits: [{role, match_score, covered_skills, missing_skills}], profile_count }
```

No LLM call and nothing persisted, so it is not rate limited like an
analysis and returns in well under a second once the model is warm. The
same scorer and the same curated profile back a typed role in the analysis
flow, which is why the two numbers agree.

---

## Authentication

JWT in an `Authorization: Bearer` header. Not cookies.

The frontend and backend live on different domains (`*.vercel.app` and
`*.onrender.com`). A cross-site cookie needs `SameSite=None; Secure`, and Safari
ITP plus common tracker blockers drop those anyway. Header tokens avoid the
entire class of problem, at the cost of being readable by JavaScript. For a
portfolio app with no payment data that trade is worth making. If this ever
handles anything sensitive, move the frontend behind the same domain and switch
to httpOnly cookies.

- Access token, 24h expiry, HS256, subject is the user id.
- No refresh token in v1. Expiry logs the user out; that is acceptable here.
- Logout is client-side token deletion. A server-side blacklist needs Redis and
  is not justified at this scale.
- Every report query filters by `user_id` from the token. Never trust an id from
  the path alone.

---

## Deployment

| Layer    | Host              | Notes                                      |
| -------- | ----------------- | ------------------------------------------ |
| Frontend | Vercel (static)    | Vite build, `VITE_API_URL` at build time    |
| Backend  | Vercel (Python)    | FastAPI function, 300 s max; migrations run by hand before deploy |
| Database | Neon (free tier)   | pooled URL for the app, direct URL for Alembic |

On Vercel there is no PDF engine (the frontend falls back to browser print)
and rate limits live in the `rate_hits` table. The Docker image and
`render.yaml` remain as an alternative that renders PDFs server-side.

All three are free tiers, described in `render.yaml` at the repo root.

**The embedding model.** In the Docker image the fastembed model is baked in at
build time, so a 512 MB instance never downloads it. On Vercel there is no image:
the model (about 65 MB, quantized) downloads to `/tmp` on a cold start, which the
function's 2 GB of memory absorbs at the cost of a few seconds.

**Cold starts.** A Vercel function that has been idle starts in a few seconds
plus that download; Neon's compute resumes in well under a second. Render's free
tier, the Docker alternative, sleeps after 15 minutes and takes 30 to 50 seconds
to wake.

**CORS** is an explicit allowlist read from env, never `*`, because credentials
are involved.

---

## What is deliberately not here

- No Redis, no Celery. Analysis is synchronous. Adding a queue means adding a
  worker dyno and a polling endpoint, for a job that finishes in 25 seconds.
- No vector database. Embeddings are computed per request and discarded. There
  is no corpus to search. pgvector becomes worth it only when resumes are matched
  against a stored pool of job postings.
- No microservices. One FastAPI app.
- No refresh tokens, no email verification, no password reset in v1.

Each of these is a reasonable v2. None of them is needed to ship.
