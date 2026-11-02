# Deployment log

A record of the attempt to put Resume Analyzer live on free hosting, in the
order things happened: what was done, what was committed, and where each
blocker appeared. No secrets are written here; where a step involved one, it
says which key, never the value.

**Goal:** a live app on free tiers only, with no paid plans.

**Status (2026-11-02): live.** Frontend
https://resume-analyzer-five-delta-75.vercel.app, API
https://resume-analyzer-6phf.vercel.app, database on Neon. Sections 1 to 7
are the path there, including the dead ends; section 8 is how it went live.

| Part | Host | State |
| --- | --- | --- |
| Database | Neon (free), AWS Singapore | ✅ live, migrated to head |
| Frontend | Vercel (Hobby, free) | ✅ deployed at https://resume-analyzer-five-delta-75.vercel.app |
| Backend API | — | ❌ not deployed: Render needs a card, Hugging Face needs PRO |

---

## 1. Production check on this machine

Before going live, the production setup was reproduced locally to match
Render's free tier as closely as possible.

- **Backend image:** built `backend/Dockerfile` as `resume-analyzer-api:local`.
- **Database:** a throwaway `postgres:16-alpine` container (`ra-pg`) on a
  private Docker network (`ra-check`), standing in for Neon.
- **API container:** `ra-api`, capped at `--memory 512m` (the free-tier
  limit), listening on `PORT=10000` the way Render sets it.
- **Frontend:** a production build with `VITE_API_URL` pointing at the
  container, served by `vite preview` on port 4173; CORS allowed only that
  origin.

Results:

| Check | Result |
| --- | --- |
| Migrations on an empty Postgres | all ran on container start |
| Health, sign-up, CORS preflight | OK |
| Career suggestions on upload | 200 in 0.1 s |
| Analysis against a role (Backend Developer) | 63%, same as the dev server; 6 keywords, 5 rewrites |
| Analysis against a pasted job description | 50% |
| History list, PDF export, direct link to `/reports` | all OK |
| Peak memory | **275 MiB of 512**, no OOM, no restarts, no 500s |

### Changes this needed (commit `3aa6cbf`)

- **Migrations on start:** Render's free tier has no pre-deploy command, so
  the Dockerfile's `CMD` became
  `alembic upgrade head && exec uvicorn ... --port ${PORT:-8000}`. With a
  single instance there is no migration race.
- **Port:** the app and the Docker `HEALTHCHECK` use `$PORT`, falling back
  to 8000 locally.
- **`render.yaml` (new):** a Blueprint describing the API as a free Docker
  web service and the frontend as a free static site, with secrets marked
  `sync: false` so they are entered in the dashboard and never stored in
  the repo. `JWT_SECRET` set to `generateValue: true`.
- **Docs:** README and ARCHITECTURE switched from "Vercel + Supabase, run
  migrations by hand" to "Render + Neon, migrations run on start".

## 2. Choosing the database: Neon

- Options weighed: Neon, Render Postgres, Supabase.
- **Chosen: Neon.** Its free tier does not expire. Render's free database is
  deleted after 30 days; Supabase pauses projects after a week idle.
- Project created in **AWS Asia Pacific 1 (Singapore)**.
- Neon's "what else does your app need?" screen: **Just Postgres**. Better
  Auth, object storage, functions, AI Gateway and realtime were all skipped:
  the app has its own auth, keeps no files, runs its backend elsewhere,
  already calls Groq and Gemini directly, and the AI Gateway needs a paid
  plan.

### Neon agent skills

- `npx neon skills -y` **failed**: the Neon CLI needs Node 22.20+, and this
  machine has Node 20.20.
- Running it under `npx -p node@22` **failed** too: the inner `npx` call
  inherited npm's exec settings.
- **Fixed** by running the cached Node 22.23 binary directly with it first on
  `PATH`. Nine skills were installed into `.claude/skills/`, with a
  `skills-lock.json`. Both are untracked and not committed. System Node was
  not changed.
- The `neon` plugin marketplace and the `neon-postgres` plugin were also
  added through `/plugin`.

## 3. Wiring Neon into the app (commit `657ede4`)

### Blocker: connection strings written into the wrong files

Neon's setup wrote two connection strings into **both** env files:

- **`backend/.env.example` (tracked by git):** the passwords there were
  masked, and nothing was committed. The extra lines were removed, and the
  file now documents the two URLs with placeholders.
- **`backend/.env` (local secrets):** a second `DATABASE_URL` pointing at
  Neon had been added below the SQLite one. The later line wins, so the next
  dev-server restart would have written local test data into the
  **production** database. The two keys were renamed to `NEON_DATABASE_URL`
  (pooled) and `NEON_DATABASE_URL_UNPOOLED` (direct). Local dev is back on
  `dev.db`.

### Blocker: the Neon prompt's steps did not fit this repo

Neon's suggested prompt ran `neon init` / `neon deploy` in the repo root.
They were skipped: the project already existed, the connection strings were
already pulled, and `neon init` would have added `neon.ts` and
`package.json` to a Python repo.

### Code changes, following Neon's guidance for this stack

- **Driver kept:** SQLAlchemy + psycopg2 suits a long-running server. The
  app uses Neon's **pooled** URL (host ends in `-pooler`).
- **`DATABASE_URL_UNPOOLED` (new setting):** Alembic uses Neon's **direct**
  URL, since migrations should not run through PgBouncer. It falls back to
  `DATABASE_URL` when unset. `%` is escaped for the ini parser.
- **`pool_pre_ping=True`** on Postgres: Neon suspends idle computes after
  5 minutes and the API host sleeps after 15, so a pooled connection can be
  dead when it is next used.
- **Region:** `render.yaml` moved from `oregon` to `singapore`, next to the
  database, to avoid about 170 ms per query across the Pacific. It has to be
  set before the service exists.
- **Docs:** `.env.example`, `render.yaml` and the README ask for both URLs.

### Blocker: migrating production

The first attempt to run `alembic upgrade head` against Neon was stopped by
Claude Code's permission check as a production change. It ran after you
approved it explicitly.

- All six migrations ran over the direct URL; Neon is at
  `c7e8f9a0b1d2 (head)`, with empty `users`, `reports` and `skill_lists`
  tables.
- The production image then started against Neon. Its own startup migration
  was a no-op, and a login for a non-existent account returned 401 through
  the pooled URL. The check was read-only, so nothing was written to
  production.
- That container was stopped afterwards, so the local frontend on :4173
  could not write to the live database by mistake.

Checks at this point: 120 backend tests passed, ruff was clean, and
`npm run build` and lint passed.

## 4. Render: blocked by a card

### Attempt 1: Blueprint

- **New → Blueprint** is not on Render's "create a service" page. It is
  under **+ New → Blueprint**, or **Blueprints → New Blueprint Instance**.
- **Blocker:** Render asked for a **credit card**.

### Attempt 2: manual Web Service + Static Site

The settings prepared for this were:

- **Web Service:** Docker, root `backend`, region Singapore, Free instance,
  health check `/api/health`.
- **Static Site:** root `frontend`, `npm ci && npm run build`, publish
  `dist`, and a `/* → /index.html` rewrite.

The whole local `.env` was pasted into the backend's environment, which
needed fixing:

| Key | Problem | Fix |
| --- | --- | --- |
| `DATABASE_URL` | was `sqlite:///./dev.db`; production would use a throwaway SQLite file and lose all data on every restart | set to the Neon pooled URL, without quotes ✅ |
| `DATABASE_URL_UNPOOLED` | missing; the app ignores the `NEON_*` names | added from the Neon direct URL ✅ |
| `CORS_ORIGINS` | was `http://localhost:5173`, so the browser would block the live frontend | set to the frontend's real URL ✅ |
| `JWT_SECRET` | same as local dev | deleted; a new one is still needed (Render's **Generate** button, or `openssl rand -hex 32`) ⚠️ |

**Blocker:** Render **kept asking for a card** for the manual services too.
Render now asks for one even on free services, to block abuse. It says the
free plan is not charged, but adding one was not an option for this
attempt.

## 5. Frontend on Vercel (done)

- Commit `c57a6ff` added `frontend/vercel.json`, an SPA rewrite so
  refreshing `/reports` does not return a 404.
- Imported `ahmadkhanraj01/resume-analyzer` at vercel.com/new: root
  directory `frontend`, preset Vite, output `dist`. No card was asked for.
- One environment variable, `VITE_API_URL`, set to
  `https://ahmadkhanraj01-resume-analyzer-api.hf.space/api`, the address the
  Hugging Face Space was going to have. It must change once the backend has
  a real home, followed by a redeploy, because Vite bakes it in at build
  time.
- **Live:** https://resume-analyzer-five-delta-75.vercel.app. The pages load,
  but sign-up and analysis cannot work until the backend is up.

## 6. Hugging Face Spaces: blocked by a paid plan

- Created a Hugging Face **Write** token named `resume-analyser`. It was
  entered only in the terminal with `hf auth login` and never pasted into
  the chat. It is saved in `~/.cache/huggingface/token`.
- Commit `ab5545a` added `deploy/hf_space.py`. It stages the committed
  `backend/` files (no `.env`, `dev.db` or tests), swaps in a Space README
  with `sdk: docker` and `app_port: 8000`, and mirrors them to the Space. A
  dry run staged 51 files correctly; the container already runs as uid 1000,
  as Spaces require.
- **Blocker:** creating the Space failed with `402 Payment Required`. Free
  accounts can host only **static** Spaces; Docker and Gradio Spaces on
  cpu-basic now need a PRO subscription. Nothing was created on the account.

## 7. Other free backend hosts (researched 2026-11-01)

Sources disagree, and several comparison sites are written by competitors.

| Option | Card? | Fit |
| --- | --- | --- |
| Render free + card for verification | card on file, free plan not charged | best fit; everything is ready and tested at 512 MB |
| Koyeb | unclear: the pricing page says "Start without credit card", but its FAQ and other sources say a card is required, possibly by region | Docker works, Singapore region available |
| SnapDeploy | no card (by its own pages) | 512 MB but only 100 running hours a month; small vendor |
| Railway | no card at sign-up | not free long term: $5 for 30 days, then $1/month |
| Vercel Python functions | no card, account already exists | PDF export would likely break (WeasyPrint needs system libraries), the embedding model downloads on cold starts, and it needs code changes |

---

## Where it stands

**Done and pushed to `main`:**

| Commit | What |
| --- | --- |
| `3aa6cbf` | free-tier Render Blueprint, migrate on container start, `$PORT` |
| `657ede4` | Neon pooled + direct URLs, `pool_pre_ping`, Singapore region |
| `c57a6ff` | Vercel SPA rewrite |
| `ab5545a` | `deploy/hf_space.py`, now unusable (Hugging Face needs PRO); remove it once a host is chosen |

**Still open:**

1. **Pick a backend host.** Try Koyeb's sign-up first. If it asks for a
   card, either add one on Render (the free plan is not charged) or rework
   the backend for Vercel.
2. **Once the backend has a URL:**
   - Set Vercel's `VITE_API_URL` to `<backend URL>/api` and redeploy.
   - Set the backend's `CORS_ORIGINS` to
     `https://resume-analyzer-five-delta-75.vercel.app`.
   - Give the backend: `DATABASE_URL` (Neon pooled), `DATABASE_URL_UNPOOLED`
     (Neon direct), `GROQ_API_KEY`, `GEMINI_API_KEY`, a **new** `JWT_SECRET`,
     `GROQ_MODEL=openai/gpt-oss-120b`, `GEMINI_MODEL=gemini-3.6-flash`.
3. **Test the live site end to end** (sign-up, career suggestions, an
   analysis, history, PDF), delete the test account, and update the README's
   "Live app" line.

**Cleanup to do:**

- Delete the Hugging Face token `resume-analyser` (Settings → Access
  Tokens), and remove `deploy/hf_space.py` from the repo.
- If Render is not used, delete any half-created Render service, since its
  environment holds your secrets.
- Local leftovers from the production check: the `ra-pg` container, the
  `ra-check` network, the `resume-analyzer-api:local` image, and the
  `vite preview` server on port 4173.
- Decide whether to commit or ignore `.claude/skills/` and
  `skills-lock.json` (the Neon skills).
- The local `.env`, including the Neon password and the Groq and Gemini
  keys, was read in this chat once, with your permission. Rotating those
  keys after the deploy is a cheap precaution.

---

## 8. Switching the backend to Vercel (2026-11-02)

With Render needing a card and Hugging Face needing PRO, the backend moved to
Vercel's Python runtime: free on Hobby, no card, and the account already
existed. Hobby limits checked against this app: 2 GB memory (peak use is
about 275 MB), 300 s per request (an analysis takes 20 to 60 s), and a
500 MB Python bundle.

What had to change, and why:

- **PDF export:** WeasyPrint needs Pango and Cairo, which Vercel's runtime
  does not have. A failed import now raises `PDF_UNAVAILABLE` (503) instead
  of the generic `PDF_RENDER_FAILED`, and the frontend opens the browser's
  print dialog. A print stylesheet hides the app chrome and shows every
  model answer; a test print came out as six clean A4 pages. Fixed on the
  way: PDF errors arrived as a Blob, so the frontend never saw their code.
- **Rate limits:** the in-memory counter would be per running copy on a
  serverless host. Against Postgres they now live in a `rate_hits` table
  (migration `d9e0f1a2b3c4`), with a per-bucket advisory lock so a burst
  cannot slip past the count. Database errors fail open. SQLite (dev,
  tests) keeps the in-memory limiter.
- **Client IP for login throttling:** behind Vercel's proxy the socket peer
  is the proxy. When `VERCEL=1` (set by Vercel), the IP comes from
  `x-real-ip`, which Vercel overwrites; it is never trusted elsewhere.
- **Config:** `backend/vercel.json` sets `maxDuration: 300` and leaves tests
  and migrations out of the bundle. Vercel finds `app` in `backend/main.py`
  on its own.
- **Migrations:** no container start on Vercel, so they are applied by hand
  with `DATABASE_URL_UNPOOLED` before a deploy that adds one.
- **Removed:** `deploy/hf_space.py`.

Checks: 126 backend tests pass (5 new rate-limit tests and a
`PDF_UNAVAILABLE` router test), the new migration upgrades and downgrades
cleanly, and frontend lint and build pass.

### Getting the API to start on Vercel

Two more failures, both read from Vercel's runtime logs:

1. **`ModuleNotFoundError: No module named 'fastapi'`:** Vercel treated
   `backend/pyproject.toml`, which held only ruff and pytest settings, as
   the dependency file and ignored `requirements.txt`. Fixed in `cdbb80c`
   by moving those settings to `ruff.toml` and `pytest.ini`.
2. **`Read-only file system (os error 30)`** while downloading the
   embedding model: only `/tmp` is writable on Vercel, and huggingface_hub
   caches under the home directory. fastembed retried for about 40 s, then
   startup failed. Fixed in `7e9831a`: when `VERCEL` is set,
   `app/__init__.py` points `HF_HOME` and `FASTEMBED_CACHE_PATH` at `/tmp`.
   A local run with an unwritable home and an empty cache downloaded the
   model cleanly.

Also along the way: the frontend's `VITE_API_URL` still pointed at the
planned Hugging Face address and had to be changed to the API's URL plus a
redeploy; Vercel's warning about the public `VITE_` prefix is expected for a
URL. The Vercel CLI (65.9.0) and the Vercel Claude Code plugin were
installed so logs could be read directly.

### Live check (2026-11-02)

| Check | Result |
| --- | --- |
| Health | `{"ok":true}` in 0.8 s |
| CORS preflight from the frontend | 200, origin allowed |
| Sign-up | 201 |
| Career suggestions | 200 in 4.2 s; Backend Developer at 63% |
| Analysis (Backend Developer) | 201 in 11.7 s; 63%, the same as local and Docker; 6 gaps, 6 keywords, 5 rewrites |
| History | 200, one report |
| PDF | 503 `PDF_UNAVAILABLE`, as designed (the frontend opens print) |
| Direct link to `/reports` | 200 |

The test report was deleted through the API. The empty test account
`livecheck-1793600761@example.com` remains, since there is no
account-deletion endpoint.

**Open:** the `rate_hits` migration (`d9e0f1a2b3c4`) was not yet applied to
Neon, so rate limits were failing open with a logged warning.
