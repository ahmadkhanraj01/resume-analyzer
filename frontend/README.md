# Frontend

React 19 + Vite. Talks to the backend over a single axios instance in
`src/api/client.js`, which attaches the bearer token and clears it on 401.

## Layout

```
src/api/         one axios instance plus auth and interview calls
src/context/     AuthProvider, the context object, and the useAuth hook
src/routes/      ProtectedRoute
src/pages/       Login, Register, NewAnalysis, History, ReportDetail
src/components/  FileDrop, CareerFit, StagedProgress, ScoreRing, SkillGapList, ...
src/lib/         errorMessages (one line per backend error code), format
src/styles/      SCSS
```

## Run locally

```bash
npm install
npm run dev        # http://localhost:5173, expects the backend on :8000
npm run build
npm run lint
```

Set `VITE_API_URL` to point at a different backend, for example the Render
URL after deploy.

## Notes

- Analysis takes 8 to 25 seconds. `StagedProgress` shows named stages
  driven by elapsed time; do not replace it with a bare spinner.
- `CareerFit` appears under the file drop once a resume is chosen. It
  calls `POST /interview/careers`, which has no LLM step and returns in a
  few seconds, so a busy label on the button is enough there. Picking a
  role fills the target box with "I want to be a …", which the backend
  routes to the same curated profile the panel scored.
- The job description box accepts as few as 10 characters so a bare role
  name gets through; `JD_MIN` mirrors `JD_MIN_LENGTH` in the backend.
- Adding a backend error code means adding a message in
  `src/lib/errorMessages.js`. A backend test fails if the two drift.
- File type is checked here for fast feedback only; the server validates by
  magic bytes.
