# Rules

Hard rules for this repository. `CLAUDE.md` tells an agent how to work here;
this file is what applies to every commit regardless of who or what makes it.

---

## Git identity and attribution

**All commits, pushes, and merges to `main` use `ahmadkhanraj01`.** No commit in
this repository is authored by, co-authored by, or attributed to an AI assistant.

Set once per clone:

```bash
git config user.name  "ahmadkhanraj01"
git config user.email "<the email on the GitHub account>"
```

Verify before the first push:

```bash
git config user.name && git config user.email
git log -1 --pretty='%an <%ae>'
```

Rules that follow from this:

- No `Co-authored-by:` trailer naming an assistant, model, or tool.
- No `Generated with ...` footer in commit messages.
- No assistant name in the commit body, PR description, or merge commit.
- If a commit lands with the wrong author, fix it before it reaches `main`:
  ```bash
  git commit --amend --reset-author --no-edit        # last commit
  git rebase -i --exec 'git commit --amend --reset-author --no-edit' main   # a range
  ```
- If it already reached `main`, leave it. Rewriting pushed history on a shared
  branch costs more than one wrong author line.

Agents write code, run tests, and prepare changes. The human runs the commit,
the push, and the merge.

---

## Branching

- `main` is always deployable. Vercel and Render build from it.
- Work happens on a branch, merged by PR. No direct commits to `main` except a
  README typo.
- Branch names: `feat/scoring-thresholds`, `fix/pdf-pagination`,
  `chore/bump-fastembed`, `docs/structure`.
- Delete the branch after merge.

---

## Commits

Conventional commits, imperative mood, no trailing period.

```
feat(scoring): weight skills by JD mention count
fix(auth): return 404 for foreign report ids instead of 403
chore(deps): pin fastembed to 0.4.2
docs(design): add error code table
```

Types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`.

- One logical change per commit. A formatting sweep and a bug fix are two.
- The body explains why, not what. The diff already says what.
- No `wip`, `fix`, `update`, or `asdf` as a complete message. If a branch has
  those, squash on merge.

---

## Pull requests

- Squash merge. `main` history stays one commit per change.
- PR description states what changed and why, and names the phase from
  `PHASES.md`.
- Every checkbox below is true before merge:
  - [ ] `ruff check .` clean
  - [ ] `pytest` passes
  - [ ] `npm run lint` clean if the frontend changed
  - [ ] no new dependency without a stated reason
  - [ ] no secret, key, or connection string in the diff
  - [ ] docs updated if the contract, structure, or architecture changed

---

## Secrets

- `.env` is in `.gitignore` from the first commit. Never removed from it.
- `.env.example` lists every key with empty values. A new env var means updating
  it in the same PR.
- No API key, database URL, or JWT secret in code, tests, fixtures, comments, or
  commit messages. Not even a placeholder that looks real.
- If a secret is ever committed, rotate it immediately. Deleting the line does
  not remove it from history, and the key is compromised the moment it is pushed.
- Production env vars live in the Render and Vercel dashboards only.

---

## Code

These repeat `CLAUDE.md` because they apply to human commits too.

- `app/services/` imports no FastAPI. No `HTTPException`, no `Request`, no
  `Depends`. Services raise domain exceptions; routers translate them.
- The LLM never produces the match score. Scoring is deterministic and lives in
  `services/scoring.py`.
- Every report query filters by the authenticated `user_id`. A foreign id returns
  404, never 403.
- Blocking work, meaning fastembed, WeasyPrint, and text extraction, goes through
  `run_in_threadpool`. Never called directly inside an `async def` handler.
- Nothing is written to disk expecting persistence. Render's filesystem is
  ephemeral.
- No DB model returned directly from a route. Map through a schema.
- `app/schemas/report.py` changes require updating the DB columns, the prompt,
  the frontend, and a migration in the same PR.
- `api/client.js` is the only file that configures axios. Components never
  import axios.

---

## Dependencies

- Pin exact versions in `requirements.txt`. No open ranges.
- A new dependency needs a one-line justification in the PR: what it replaces and
  why the stdlib or an existing package will not do.
- The deployment target has 512 MB of memory and the image already carries an
  ONNX model. Treat every package as a memory cost.
- No Redis, Celery, vector database, or second service. `ARCHITECTURE.md` records
  why each was excluded. If one becomes necessary, change that document first.

---

## Documentation

- `ARCHITECTURE.md`, `DESIGN.md`, `STRUCTURE.md`, `PHASES.md` are kept current.
  A stale architecture doc is worse than none.
- Tick phase boxes in `PHASES.md` as part of the merge, not later.
- Writing style: no em dashes, concise, specific, no filler openers.
- Comments explain why. `# retry once with the validation error so the model can
  self-correct` is useful; `# retry` is not.

---

## Testing

- `services/scoring.py` is deterministic, so assert exact scores.
- `services/llm.py` is tested with mocked providers, including one malformed
  response proving the retry path runs.
- No test hits a live LLM API.
- A bug fix comes with the test that would have caught it.
