# Sample

Local inputs for manual smoke testing the full pipeline against the dev
server. Files here are not test fixtures; the automated fixtures live in
`backend/tests/fixtures/`.

Personal documents placed here should not be committed. Only this README is
tracked.

Example run against a local backend:

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"me@example.com","password":"testpass123"}' | jq -r .access_token)

curl -X POST localhost:8000/api/interview/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "resume=@Sample/your_resume.pdf" \
  -F "job_description=<Sample/jd.txt"
```

Rank the same resume against every curated role profile (no LLM, no report):

```bash
curl -X POST localhost:8000/api/interview/careers \
  -H "Authorization: Bearer $TOKEN" \
  -F "resume=@Sample/your_resume.pdf"
```

Or type a target instead of a posting; a role the app knows scores against
its curated profile, so the number matches the career-fit panel:

```bash
curl -X POST localhost:8000/api/interview/ \
  -H "Authorization: Bearer $TOKEN" \
  -F "resume=@Sample/your_resume.pdf" \
  -F "job_description=I want to be an AI Engineer."
```
