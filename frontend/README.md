# Frontend

React 19 + Vite. Talks to the backend over a single axios instance in
`src/api/client.js`, which attaches the bearer token and clears it on 401.

## Layout

```
src/api/         one axios instance plus auth and interview calls
src/context/     AuthProvider, the context object, and the useAuth hook
src/routes/      ProtectedRoute
src/pages/       Login, Register, NewAnalysis, History, ReportDetail
src/components/  FileDrop, CareerFit, StagedProgress, ScoreTape, ResumeSuggestions, ...
src/lib/         errorMessages (one line per backend error code), format
src/styles/      SCSS, including the print stylesheet at the end of main.scss
vercel.json      rewrites client-side routes (/reports, /reports/:id) to index.html
```

## Run locally

```bash
npm install
npm run dev        # http://localhost:5173, expects the backend on :8000
npm run build
npm run lint
```

Set `VITE_API_URL` (in `.env.local`, see `.env.example`) to point at a
different backend. It is baked into the bundle at build time, so changing it
means rebuilding.

## Deploying on Vercel (what runs live)

Import the repository as a Vercel project with root directory `frontend`
and preset Vite (build `npm run build`, output `dist`). Set one variable:

- `VITE_API_URL`: the API's URL plus `/api`, for example
  `https://resume-analyzer-6phf.vercel.app/api`.

Vercel warns that the `VITE_` prefix exposes the value to the browser.
That is expected and fine for a URL, and the prefix is required: Vite only
passes `VITE_` variables into the bundle. Never put an API key, `JWT_SECRET`,
or a database URL in this project. After changing the variable, redeploy;
saving it alone does not rebuild the bundle.

## Notes

- Analysis takes 8 to 25 seconds. `StagedProgress` shows named stages
  driven by elapsed time; do not replace it with a bare spinner.
- `CareerFit` appears under the file drop and scores the resume as soon
  as it is chosen. It calls `POST /interview/careers`, which has no LLM
  step and returns in a few seconds, so a small inline spinner is enough
  there. "Use this role" fills the target box with "I want to be a …",
  which the backend routes to the same curated profile the panel scored.
- Fonts are Bricolage Grotesque (headings) and Atkinson Hyperlegible
  (body), loaded from Google Fonts in `index.html`. Palette tokens live in
  `src/styles/_variables.scss`.
- The job description box accepts as few as 10 characters so a bare role
  name gets through; `JD_MIN` mirrors `JD_MIN_LENGTH` in the backend.
- Adding a backend error code means adding a message in
  `src/lib/errorMessages.js`. A backend test fails if the two drift.
- File type is checked here for fast feedback only; the server validates by
  magic bytes.
- "Download PDF" asks the API for a PDF. If the API answers
  `PDF_UNAVAILABLE` (it does on Vercel, which has no PDF engine), it calls
  `window.print()` instead. The print styles hide the navigation, side rail
  and buttons, show every model answer, and keep cards whole across pages,
  so Save as PDF gives a clean report. Model answers are always rendered
  and hidden with the `hidden` attribute for this reason.
- PDF errors come back as a Blob because of `responseType: "blob"`;
  `downloadReportPdf` parses them back to JSON so their codes reach
  `messageForError`.
