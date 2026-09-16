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

```
                 ┌──────────────────────────┐
                 │   React + Vite (Vercel)  │
                 │   axios + Bearer token   │
                 └───────────┬──────────────┘
                             │  HTTPS / JSON
                             ▼
                 ┌──────────────────────────┐
                 │   FastAPI (Render)       │
                 │                          │
                 │   api/      auth,        │
                 │             interview    │
                 │   services/ extract      │
                 │             scoring      │
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
  skill_gaps        jsonb
  technical_qs      jsonb
  behavioral_qs     jsonb
  preparation_plan  jsonb
  created_at        timestamptz
```

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
4. Classify: above 0.75 covered, 0.55 to 0.75 partial, below 0.55 missing.
5. Aggregate into a 0 to 100 score, weighting skills the JD repeats.

No network call, no temperature, no drift. The same inputs always produce the
same score, which is the whole point.

Thresholds live in `config.py`, not scattered through the module, because they
will need tuning against real resumes.

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
  ├─ scoring.score(text, jd)    embeddings, deterministic
  ├─ llm.generate(text, jd, scoring_result)
  │     └─ Groq -> validate -> (retry once) -> fallback Gemini
  ├─ persist Report
  └─ 201 { report }
```

Total latency is dominated by the LLM call, typically 8 to 25 seconds. The
frontend must show progress, not a spinner that looks frozen.

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
| Frontend | Vercel            | static build, `VITE_API_URL` at build time |
| Backend  | Render (Docker)   | uvicorn, single worker on free tier        |
| Database | Supabase or Neon  | pooled connection string                   |

**Docker matters here.** The fastembed model is baked into the image at build
time rather than downloaded on first request. Without that, the first user after
every cold start waits for a 100 MB download, and on a 512 MB instance it may
simply OOM.

**Cold starts.** Render's free tier sleeps after 15 minutes idle and takes 30 to
50 seconds to wake. Either accept it and say so in the README, or add an
external cron ping every 10 minutes.

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
