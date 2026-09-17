# Frontend

React 19 + Vite. Talks to the backend over a single axios instance in
`src/api/client.js`, which attaches the bearer token and clears it on 401.

## Layout

```
src/api/         one axios instance plus auth and interview calls
src/context/     AuthProvider, the context object, and the useAuth hook
src/routes/      ProtectedRoute
src/pages/       Login, Register, NewAnalysis, History, ReportDetail
src/components/  FileDrop, StagedProgress, ScoreRing, SkillGapList, ...
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
- Adding a backend error code means adding a message in
  `src/lib/errorMessages.js`. A backend test fails if the two drift.
- File type is checked here for fast feedback only; the server validates by
  magic bytes.
