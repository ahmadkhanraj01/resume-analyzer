# Design

Contracts, data shapes, and interface decisions. `ARCHITECTURE.md` says how the
system is put together; this says what it actually does.

---

## Product scope

**In scope for v1**

- Register, log in, log out
- Upload a resume (PDF or DOCX), paste a job description and self description
- Receive a report: match score, skill gaps, technical questions, behavioral
  questions, day-by-day preparation plan
- List past reports, open one, export it as PDF

**Explicitly out of scope for v1**

- Resume rewriting or generation
- Multi-resume comparison
- Job scraping from a URL
- Team or recruiter accounts
- Password reset, email verification

---

## API

Base: `/api`. All responses JSON except the PDF endpoint.

### Auth

| Method | Path             | Auth | Body                | Returns              |
| ------ | ---------------- | ---- | ------------------- | -------------------- |
| POST   | `/auth/register` | no   | `{email, password}` | `{access_token, user}` |
| POST   | `/auth/login`    | no   | `{email, password}` | `{access_token, user}` |
| GET    | `/auth/me`       | yes  | -                   | `{user}`             |

Register logs the user in directly. Making someone log in again immediately
after signing up is friction with no benefit.

Password rules: minimum 8 characters, no composition requirements. Length is
what matters; forced symbols produce `Password1!` and nothing else.

### Interview

| Method | Path                        | Auth | Body                          | Returns   |
| ------ | --------------------------- | ---- | ----------------------------- | --------- |
| POST   | `/interview/`               | yes  | multipart                     | `{report}` |
| GET    | `/interview/`               | yes  | `?limit=20&offset=0`          | `{items, total}` |
| GET    | `/interview/{id}`           | yes  | -                             | `{report}` |
| DELETE | `/interview/{id}`           | yes  | -                             | `204`     |
| POST   | `/interview/{id}/pdf`       | yes  | -                             | PDF bytes |

Multipart fields on `POST /interview/`:

```
resume            file, PDF or DOCX, max 5 MB
job_description   text, 50 to 20000 chars
self_description  text, 0 to 2000 chars, optional
```

The list endpoint returns a trimmed shape (id, title, match_score, created_at)
rather than full reports. A history page does not need 8 KB of JSON per row.

### Errors

One shape everywhere, produced by a single exception handler:

```json
{ "error": { "code": "LLM_UNAVAILABLE", "message": "Analysis failed. Try again." } }
```

| Code                   | HTTP | When                                       |
| ---------------------- | ---- | ------------------------------------------ |
| `VALIDATION_ERROR`     | 422  | bad request body, includes `fields`        |
| `INVALID_CREDENTIALS`  | 401  | login failure                              |
| `TOKEN_INVALID`        | 401  | missing, malformed, or expired token       |
| `NOT_FOUND`            | 404  | report id absent or owned by someone else  |
| `FILE_TOO_LARGE`       | 413  | over 5 MB                                  |
| `UNSUPPORTED_FILE`     | 415  | not PDF or DOCX                            |
| `EXTRACTION_FAILED`    | 422  | file parsed but produced no usable text    |
| `LLM_UNAVAILABLE`      | 503  | both providers failed                      |
| `PDF_RENDER_FAILED`    | 500  | WeasyPrint could not render the report     |
| `RATE_LIMITED`         | 429  | over the per-user analysis limit           |

A report id belonging to another user returns 404, not 403. 403 confirms the id
exists, which leaks information.

`EXTRACTION_FAILED` matters more than it looks. Scanned-image resumes are common
and produce zero text. The message must tell the user why, not fail generically.

---

## Report contract

This Pydantic model is the single source of truth. The LLM prompt embeds its
schema, the response is validated against it, the DB columns mirror it, and the
frontend types match it. One definition, four consumers.

```python
class Severity(str, Enum):
    critical = "critical"
    moderate = "moderate"
    minor    = "minor"

class SkillGap(BaseModel):
    skill:      str
    severity:   Severity
    similarity: float = Field(ge=0, le=1)   # from scoring, not the LLM
    advice:     str   = Field(max_length=300)

class Question(BaseModel):
    question:  str
    intention: str                          # what the interviewer is probing
    answer:    str                          # a model answer to study

class PrepDay(BaseModel):
    day:   int = Field(ge=1, le=14)
    focus: str
    tasks: list[str] = Field(min_length=1, max_length=5)

class InterviewReport(BaseModel):
    title:             str
    match_score:       int = Field(ge=0, le=100)   # overwritten by scoring
    skill_gaps:        list[SkillGap]        = Field(max_length=12)
    technical_qs:      list[Question]        = Field(max_length=10)
    behavioral_qs:     list[Question]        = Field(max_length=6)
    preparation_plan:  list[PrepDay]         = Field(max_length=14)
```

Every list has an upper bound. Without one, a verbose model returns forty
questions, the response takes 60 seconds, and the UI becomes unreadable.

`intention` is included because a question without knowing what is being tested
is far less useful for preparation.

---

## Scoring design

### Skill extraction

Skills come out of the job description, not a fixed taxonomy. A hardcoded list
cannot keep up with tooling, and every miss is invisible to the user.

Two-pass approach:

1. Regex and n-gram pass against a seed list of known technologies. Cheap, high
   precision, catches the obvious.
2. LLM pass returning a plain string list of required skills. Loose, high recall.

Union the two, deduplicate case-insensitively, cap at 25. This is the one place
the LLM feeds into scoring, and only to name skills, never to grade them.

### Similarity

Resume text is chunked at roughly 200 tokens with 50 token overlap. Overlap
matters: a skill mentioned across a line break is otherwise split in half and
scores low in both chunks.

Each skill is embedded, compared against every chunk by cosine similarity, and
assigned the maximum. Max, not mean, because a skill appearing once in a long
resume is still present.

### Thresholds

```python
COVERED_THRESHOLD  = 0.75
PARTIAL_THRESHOLD  = 0.55
```

Above covered, the skill is present. Between the two, partial, mapped to
`moderate`. Below partial, missing, mapped to `critical`. These are starting
values and need calibration against twenty real resume and JD pairs before they
mean anything. Record the calibration set in the repo.

### Aggregate score

```
weight(skill)  = 1 + 0.5 * min(mentions_in_jd - 1, 2)
raw            = Σ weight * min(similarity / COVERED_THRESHOLD, 1.0)
match_score    = round(100 * raw / Σ weight)
```

A skill named three times in a JD counts double a skill named once. Similarity
is capped at 1.0 so an exact match cannot inflate past its weight.

The score is never rounded to a friendly number and never floored at some
minimum. A 20% match should display as 20%.

---

## Prompt design

One prompt, one call, structured output. Not a chain, because each extra hop
adds latency and a new failure point for no accuracy gain at this scope.

Structure:

1. Role and task, one paragraph.
2. The JSON schema, verbatim, with an instruction to emit JSON only and no
   markdown fences.
3. Resume text, truncated to 6000 characters.
4. Job description, truncated to 4000 characters.
5. Self description, if present.
6. The scoring output, as the authoritative list of covered and missing skills,
   with an explicit instruction to build questions and the plan around the gaps
   rather than re-deriving them.

Truncation is by characters and applied at the tail. A resume's first 6000
characters carry the recent roles; the tail is early-career detail.

Validation and retry:

```
response -> strip fences -> model_validate_json
  ok       -> return
  fail     -> retry once, appending the validation error verbatim
  fail x2  -> next provider
  all fail -> LLM_UNAVAILABLE
```

The retry works because the model is told exactly which field it got wrong. A
blind retry with the same prompt usually reproduces the same error.

---

## Frontend design

### Routes

```
/                     redirect to /new or /login
/login                public
/register             public
/new                  protected, the upload form
/reports              protected, history list
/reports/:id          protected, detail view
```

### The waiting problem

Analysis takes 8 to 25 seconds, sometimes longer on a cold backend. A generic
spinner reads as a hang, and users refresh, which loses the request.

Show staged progress instead, driven by elapsed time rather than real events:

```
0s    Reading your resume
3s    Matching skills against the role
8s    Generating interview questions
18s   Building your preparation plan
```

This is honest about the pipeline order even though it is not wired to actual
callbacks. Disable the submit button and warn before unload while in flight.

### Report view

Score first, as a number with a short qualitative label, then gaps, then
questions, then the plan. Users want the verdict before the detail.

Skill gaps sort by severity, not alphabetically. Questions collapse their model
answers by default, so the page is scannable and the user can self-test before
revealing.

### Error states

Every failure code maps to a specific message. `EXTRACTION_FAILED` in particular
must say that the file appears to be a scanned image and suggest a text-based
PDF. A generic "something went wrong" for that case guarantees a repeat attempt
with the same file.

---

## Limits

| Limit                         | Value | Reason                       |
| ----------------------------- | ----- | ---------------------------- |
| Upload size                   | 5 MB  | resumes are under 1 MB       |
| Analyses per user per hour    | 10    | LLM quota protection         |
| Analyses per user per day     | 30    | same                         |
| JD length                     | 20k   | truncated to 4k for prompting |
| Reports retained per user     | 50    | oldest pruned                |

Rate limiting is in-process for v1, using a dict keyed by user id. Single worker
on a single instance means that is correct. It becomes wrong the moment a second
worker exists, so the limiter lives behind one interface that can be swapped for
Redis without touching the routes.

---

## Security

- Passwords hashed with bcrypt, cost 12. Never selected in a default query.
- Every report access filtered by `user_id` from the token.
- File type validated by magic bytes, not by the filename extension.
- Uploads are never written to disk and never re-served.
- No user text is interpolated into f-strings that reach the LLM as
  instructions; resume and JD content go in clearly delimited blocks so a
  "ignore previous instructions" line in a resume lands as data.
- Secrets from env only. `.env` in `.gitignore` from the first commit.
- CORS allowlist explicit, no wildcard.
