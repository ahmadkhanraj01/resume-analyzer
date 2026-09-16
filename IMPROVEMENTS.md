# Improvements

Suggestions for improving the current build, ordered by priority. Items in
"Bugs" were reproduced against the code as it stands; everything else is a
recommendation. Check `PHASES.md` before starting anything that belongs to a
later phase.

---

## 1. Bugs (fix first)

Each of these returns a raw 500 instead of a clean error from `DESIGN.md`.

### Passwords over 72 bytes crash registration

`RegisterIn.password` allows up to 128 characters, but bcrypt 5.x raises
`ValueError: password cannot be longer than 72 bytes`. A long passphrase
(or a short one with multi-byte characters) produces a 500.

**Fix:** cap `max_length` at 72 in `schemas/auth.py` and validate the UTF-8
byte length, not the character count. Add a test for it.

### Corrupted or disguised files crash extraction

`extract._sniff` checks magic bytes only. Two cases pass the sniff and then
blow up inside the parser:

- A corrupted PDF (`%PDF-` header, broken body) raises `PdfStreamError`.
- Any zip file (`.xlsx`, `.pptx`, a plain `.zip`) starts with `PK` and raises
  `KeyError` inside python-docx.

**Fix:** wrap `_extract_pdf` and `_extract_docx` in `try/except` and raise
`UnsupportedFileError` (or `ExtractionFailedError`). For DOCX, also confirm
the archive contains `word/document.xml` before parsing.

### PDF export has no error handling

If WeasyPrint fails (missing native libraries, a template error), the
exception escapes `export_pdf` as a 500 with no useful message.

**Fix:** add a `PdfRenderError` domain exception, catch it in `pdf.py`, and
add it to the error table in `DESIGN.md` and `lib/errorMessages.js`.

### Skill gap numbers can come from the LLM

In `services/analysis.py`, scoring's severity and similarity are copied onto
the LLM's `skill_gaps` only when the skill names match. If the model renames
a skill ("Postgres" vs "PostgreSQL") or invents one, that gap keeps the
model's own numbers. This breaks the rule that the LLM never grades.

**Fix:** build `skill_gaps` from the scoring result, and take only the
`advice` text from the LLM, matched by name. Skills the LLM wrote about that
scoring never saw are dropped.

### Uploads are fully read before the size check

`await resume.read()` loads the whole file into memory, then checks the size.
A 500 MB upload is read in full first, which matters on a 512 MB instance.

**Fix:** read at most `max_upload_bytes + 1` bytes and reject if that limit
is hit.

---

## 2. Correctness and robustness

- **Rate limiter race.** `check()` runs before the analysis and `record()`
  after it finishes, 8 to 25 seconds later. A user can fire many requests in
  parallel and all of them pass the check. Record the hit up front (and
  optionally refund it on failure).
- **DB session used across threads.** `_prune_old_reports` runs through
  `run_in_threadpool` with the request's session. SQLAlchemy sessions are not
  thread-safe. Prune is fast; run it inline, or give it its own session.
- **Naive datetimes.** Models store `datetime.now(UTC)` in a `DateTime`
  column without `timezone=True`, so the offset is lost. Use
  `DateTime(timezone=True)` (`timestamptz` in Postgres, matching
  `ARCHITECTURE.md`) and add a migration.
- **JSON columns are nullable** in the migration even though the app always
  writes a list. Make them `NOT NULL` with a `'[]'` server default.
- **Embedding model loads on the first request**, not at startup, because
  `_model()` is lazily cached. The first analysis after every cold start pays
  the load time on top of Render's wake-up. Call `scoring._model()` in the
  `lifespan` hook.
- **Single-letter seed skills.** `C` and `R` in `skill_seeds.txt` match
  initialisms like "R&D", and the literal-mention floor then marks them as
  covered. Either drop them from the seed list or require stricter context.

---

## 3. Performance and cost

- **Two LLM round trips per analysis.** Skill extraction and report
  generation are separate calls. Run skill extraction in parallel with text
  extraction, or cache it per JD hash, since the same JD is often analyzed
  more than once.
- **Warn on long analyses.** Log how long each stage takes (extract, skills,
  score, LLM). Without numbers, there's no way to tell whether a slow request
  was Groq, Gemini fallback, or a cold model load.
- **Silence the google-genai AFC warning** by passing an explicit config that
  disables automatic function calling. It prints on every Gemini call and
  clutters logs.
- **Reuse provider clients.** `Groq(...)` and `genai.Client(...)` are created
  on every call. Create them once per process.

---

## 4. Security

- **Enforce a minimum `JWT_SECRET` length** (32 bytes) in `config.py`. PyJWT
  already warns about short keys in the test run.
- **Drop `allow_credentials=True` from CORS.** Auth is a bearer header, not a
  cookie, so credentials mode isn't needed and only widens what the CORS
  policy allows.
- **Login timing.** `login` skips bcrypt when the email doesn't exist, so
  response time reveals which emails are registered. Verify against a dummy
  hash in that branch.
- **Rate limit auth endpoints.** Register and login have no limit, so
  password guessing is unthrottled.
- **Run the container as a non-root user** and add a `HEALTHCHECK` pointing at
  `/api/health`.

---

## 5. Frontend

- **Handle the LLM_UNAVAILABLE case in place.** Right now a failed analysis
  drops the user back to an empty-looking form. Keep their file and JD in
  state and offer a "Try again" button.
- **History pagination.** The API supports `limit` and `offset`, but the
  History page only ever loads the first 20.
- **404 route.** Unknown URLs render a blank page. Add a catch-all route.
- **Errors on ReportDetail replace the whole page**, including after a failed
  PDF download. Show download and delete errors inline and keep the report
  visible.
- **DOCX type check.** Some browsers report an empty MIME type for `.docx`, so
  `FileDrop` rejects valid files. Fall back to the extension when `type` is
  empty; the server still validates by magic bytes.
- **Split `useAuth` into its own file** to clear the fast-refresh lint
  warning.
- **Replace `window.confirm`** for delete with an in-page confirmation.

---

## 6. Testing and tooling

- **Tests for every bug in section 1**, per `RULES.md`: a bug fix comes with
  the test that would have caught it.
- **Run the suite against Postgres at least once.** Everything so far ran on
  SQLite; JSONB, timezone handling, and constraint errors behave differently.
- **Frontend tests.** None exist. Start with `AuthContext` (no login flash)
  and `lib/errorMessages.js` (every backend code has a message).
- **A contract test** that every error code in `DESIGN.md` exists in both
  `core/exceptions.py` and `lib/errorMessages.js`, so they can't drift.
- **Build the Docker image locally** before the first Render deploy. It has
  never been built, and WeasyPrint's system libraries are the most likely
  break.
- **CI** is deferred in `PHASES.md`, but a single workflow running `pytest`,
  `ruff`, and `npm run lint` on every PR covers the `RULES.md` merge
  checklist automatically.

---

## 7. Product ideas (v2, out of scope for now)

These are listed as out of scope or deferred in `DESIGN.md` and `PHASES.md`.
They're here so they aren't lost, not as a plan.

- Re-score an existing report against an edited JD without re-uploading
  (`resume_text` is already stored for this).
- Show covered skills separately from gaps in the report view.
- Compare one resume against several JDs.
- Password reset and email verification.
- Threshold calibration against 20 real resume and JD pairs, committed to
  `docs/calibration/`.
