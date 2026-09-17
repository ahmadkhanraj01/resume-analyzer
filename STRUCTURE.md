# Directory structure

Every file, what lives in it, and what must not. Create files as their phase
arrives rather than stubbing the whole tree on day one; empty modules rot.

Phase numbers in brackets refer to `PHASES.md`.

---

## Root

```
resume-analyzer/
├── backend/
├── frontend/
├── docs/
│   └── calibration/              [9] fixture resume + JD pairs for thresholds
├── .gitignore
├── README.md                     public-facing: what it is, live link, setup
├── ARCHITECTURE.md
├── DESIGN.md
├── STRUCTURE.md                  this file
├── PHASES.md
├── RULES.md
└── CLAUDE.md
```

No root `package.json`, no workspace config, no Docker Compose. The two halves
deploy independently and share nothing but the API contract.

---

## Backend

```
backend/
├── main.py                       [0] app factory only
├── Dockerfile                    [0]
├── .dockerignore                 [0]
├── requirements.txt              [0]
├── .env.example                  [0] every key, no values
├── pyproject.toml                [0] ruff + pytest config
├── alembic.ini                   [1]
├── migrations/                   [1] alembic, versions/ committed
│
├── app/
│   ├── __init__.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py             [1] pydantic-settings. Only place os.environ is read.
│   │   ├── security.py           [2] bcrypt hash/verify, JWT encode/decode
│   │   ├── deps.py               [2] get_db, get_current_user
│   │   ├── exceptions.py         [2] domain exceptions + the handler
│   │   └── limiter.py            [6] rate limiter behind one interface
│   │
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py            [1] engine, SessionLocal
│   │   └── models.py             [1] User, Report
│   │
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py               [2] RegisterIn, LoginIn, TokenOut, UserOut
│   │   ├── report.py             [5] InterviewReport + nested. THE contract.
│   │   ├── career.py             [10] CareerFit, CareerFitOut
│   │   └── common.py             [2] ErrorOut, Paginated
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── extract.py            [3] bytes -> text
│   │   ├── scoring.py            [4] embeddings, similarity, aggregate
│   │   ├── skills.py             [4] JD -> skill list, regex + LLM union
│   │   ├── llm.py                [5] provider chain, validation, retry
│   │   ├── prompts.py            [5] prompt templates, no logic
│   │   ├── analysis.py           [6] orchestrates extract -> skills -> score -> llm
│   │   ├── careers.py            [10] ranks a resume against role_profiles.json
│   │   └── pdf.py                [8] Jinja2 + WeasyPrint
│   │
│   ├── templates/
│   │   ├── report.html.j2        [8]
│   │   └── report.css            [8] print stylesheet
│   │
│   ├── data/
│   │   ├── skill_seeds.txt       [4] known technology names, one per line
│   │   └── role_profiles.json    [10] curated skill lists per role, plus aliases
│   │
│   └── api/
│       ├── __init__.py
│       ├── router.py             [2] mounts sub-routers under /api
│       ├── health.py             [0]
│       ├── auth.py               [2]
│       └── interview.py          [6]
│
└── tests/
    ├── conftest.py               [2] test db, client, auth fixtures
    ├── fixtures/
    │   ├── resume_sample.pdf     [3]
    │   ├── resume_sample.docx    [3]
    │   ├── resume_scanned.pdf    [3] must raise ExtractionError
    │   └── jd_sample.txt         [4]
    ├── test_extract.py           [3]
    ├── test_scoring.py           [4] exact score assertions
    ├── test_llm.py               [5] mocked providers, malformed response
    ├── test_auth.py              [2]
    └── test_interview.py         [6] includes cross-user 404
```

### Backend rules per directory

**`core/`** is imported by everything and imports nothing from `app`. Circular
imports start here. `config.py` is the only module that reads the environment.

**`db/`** knows nothing about HTTP. Models are SQLModel tables. No validation
logic lives here; that is `schemas/`.

**`schemas/`** holds Pydantic models for request and response bodies. Never
return a `db/models.py` object directly from a route; map it through a schema so
`password_hash` cannot leak by accident.

**`services/`** imports no FastAPI. No `HTTPException`, no `Request`, no
`Depends`. Services raise from `core/exceptions.py`; routers translate. Every
service module must be runnable from a plain `python -c` script. That property
is the whole reason the layer exists.

**`api/`** routers are thin. Validate, call a service, persist, return. Twenty
lines is the smell threshold.

**`prompts.py` separate from `llm.py`** because prompts change constantly and
diffing them against retry and fallback logic in the same file is miserable.

**`skills.py` separate from `scoring.py`** because skill extraction is the one
place the LLM touches the scoring path. Isolating it keeps `scoring.py`
deterministic and unit-testable with no mocks.

**`analysis.py`** composes extract, skills, scoring, and llm into the one
blocking call `api/interview.py` runs through `run_in_threadpool`. Added so
the create-report route stays under the ~20 line threshold `CLAUDE.md` sets
for "this belongs in a service" instead of inlining four service calls in
the router body.

---

## Frontend

```
frontend/
├── index.html                    [0]
├── package.json                  [0]
├── vite.config.js                [0]
├── .env.example                  [0] VITE_API_URL
├── eslint.config.js              [0] flat config; ESLint 9+ dropped .eslintrc
│
├── public/
│   └── favicon.svg
│
└── src/
    ├── main.jsx                  [7] root render, router, providers
    ├── App.jsx                   [7] route table
    │
    ├── api/
    │   ├── client.js             [7] the ONLY axios instance
    │   ├── auth.js               [7] register, login, me
    │   └── interview.js          [7] create, list, get, remove, pdf, careers
    │
    ├── context/
    │   └── AuthContext.jsx       [7] user, token, loading, login, logout
    │
    ├── routes/
    │   └── ProtectedRoute.jsx    [7] waits for loading before redirecting
    │
    ├── pages/
    │   ├── Login.jsx             [7]
    │   ├── Register.jsx          [7]
    │   ├── NewAnalysis.jsx       [7] upload form
    │   ├── History.jsx           [7]
    │   └── ReportDetail.jsx      [7]
    │
    ├── components/
    │   ├── FileDrop.jsx          [7] drag-drop, client-side size/type check
    │   ├── StagedProgress.jsx    [7] timed messages during analysis
    │   ├── ScoreRing.jsx         [7]
    │   ├── SkillGapList.jsx      [7] sorted by severity
    │   ├── CareerFit.jsx         [10] top roles for the uploaded resume
    │   ├── QuestionCard.jsx      [7] collapsed answer by default
    │   ├── PrepPlan.jsx          [7]
    │   ├── ErrorBanner.jsx       [7] maps error codes to messages
    │   └── Spinner.jsx           [7]
    │
    ├── lib/
    │   ├── errorMessages.js      [7] code -> human string, one object
    │   └── format.js             [7] dates, score labels
    │
    └── styles/
        ├── main.scss             [7]
        └── _variables.scss       [7]
```

### Frontend rules

**`api/client.js` is the only file that configures axios.** Request interceptor
attaches the bearer token, response interceptor catches 401 and clears auth.
Components never import axios directly. When a component calls axios itself, the
token handling silently stops applying to that one call.

**`api/*.js` wraps endpoints, components call those.** A component should never
contain a URL string.

**`lib/errorMessages.js` is one flat object** keyed by the codes in `DESIGN.md`.
Adding a backend error code means adding a line here in the same PR, otherwise
users get a fallback message for a case you specifically handled.

**`components/` holds presentational pieces.** Data fetching lives in pages. The
exception is nothing; if a component needs data, the page passes it down.

---

## Naming

- Python: `snake_case` files, `PascalCase` classes.
- React: `PascalCase.jsx` for components, `camelCase.js` for everything else.
- Test files mirror the module: `services/scoring.py` to `tests/test_scoring.py`.
- Never `utils.py` or `helpers.js`. Those become dumping grounds. Name the file
  after what it does, and if nothing fits, the function belongs somewhere else.

---

## Growth rules

- A `services/` module over roughly 300 lines splits by responsibility, not by
  arbitrary line count.
- A new top-level backend directory needs a reason written in `ARCHITECTURE.md`.
- A second FastAPI app, a worker process, or a shared package between frontend
  and backend is out of scope. `ARCHITECTURE.md` explains why.
- `frontend/src/hooks/` is the one addition likely to be justified, around the
  time three components need the same fetch-and-loading pattern. Not before.
