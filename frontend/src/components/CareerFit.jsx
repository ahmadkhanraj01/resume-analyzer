import { useEffect, useState } from "react";
import { suggestCareers } from "../api/interview";
import { messageForError } from "../lib/errorMessages";

const TOP_N = 5;

// Ranks the uploaded resume against the curated role profiles as soon as a
// file is chosen. Never calls the LLM, so it is a few seconds at most; a
// plain busy state is enough here, unlike the full analysis.
export default function CareerFit({ file, onPick }) {
  // Bumped by "Try again" so the effect refetches for the same file.
  const [attempt, setAttempt] = useState(0);
  // Each outcome remembers which file and attempt it answers, so loading is
  // derived (no outcome for the current pair yet) instead of set in the effect.
  const [outcome, setOutcome] = useState({ file: null, attempt: -1, data: null, error: "" });
  const [picked, setPicked] = useState({ file: null, role: null });

  useEffect(() => {
    if (!file) return;
    // A slow response for a replaced file must not overwrite the newer one.
    let current = true;
    suggestCareers(file)
      .then((data) => current && setOutcome({ file, attempt, data, error: "" }))
      .catch(
        (err) =>
          current && setOutcome({ file, attempt, data: null, error: messageForError(err) })
      );
    return () => {
      current = false;
    };
  }, [file, attempt]);

  if (!file) return null;

  const fresh = outcome.file === file && outcome.attempt === attempt;
  const loading = !fresh;
  const result = fresh ? outcome.data : null;
  const error = fresh ? outcome.error : "";
  const pickedRole = picked.file === file ? picked.role : null;

  function pick(role) {
    setPicked({ file, role });
    onPick(role);
  }

  return (
    <section className="career-fit" aria-live="polite">
      <div className="career-fit__head">
        <div>
          <h2>Suggested roles</h2>
          <p className="section-lead">
            Your resume scored against typical postings for common roles. Pick one to analyze, or
            paste a specific job description below.
          </p>
        </div>
      </div>

      {loading && (
        <div className="career-fit__loading">
          <span className="spinner career-fit__spinner" aria-hidden="true" />
          <span>Matching your resume to roles…</span>
        </div>
      )}

      {error && (
        <p className="field-error">
          {error}{" "}
          <button type="button" className="button--secondary" onClick={() => setAttempt((a) => a + 1)}>
            Try again
          </button>
        </p>
      )}

      {result && (
        <ol className="career-fit__list">
          {result.fits.slice(0, TOP_N).map((fit) => (
            <li key={fit.role} className="career-fit__item">
              <div className="career-fit__row">
                <span className="score-pill">
                  <span className="mini-tape" style={{ "--score": fit.match_score }} />
                  {fit.match_score}%
                </span>
                <span className="career-fit__role">{fit.role}</span>
                <button
                  type="button"
                  className={
                    pickedRole === fit.role ? "career-fit__use" : "career-fit__use button--secondary"
                  }
                  onClick={() => pick(fit.role)}
                  aria-pressed={pickedRole === fit.role}
                >
                  {pickedRole === fit.role ? "Selected" : "Use this role"}
                </button>
              </div>
              <div className="career-fit__skills">
                {fit.covered_skills.length ? (
                  <>
                    <span className="career-fit__label">On your resume:</span>{" "}
                    {fit.covered_skills.join(", ")}
                  </>
                ) : (
                  <span className="career-fit__label">Nothing from this profile yet.</span>
                )}
              </div>
            </li>
          ))}
        </ol>
      )}
      {result && (
        <p className="career-fit__foot">
          Top {TOP_N} of {result.profile_count} roles. Scores are the share of a typical
          posting&apos;s skills your resume already names, so a strong resume for a role
          usually lands between 50% and 80%.
        </p>
      )}
    </section>
  );
}
