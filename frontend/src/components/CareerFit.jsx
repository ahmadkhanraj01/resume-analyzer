import { useState } from "react";
import { suggestCareers } from "../api/interview";
import { messageForError } from "../lib/errorMessages";

const TOP_N = 5;

function tone(score) {
  return score >= 65 ? "good" : score >= 40 ? "partial" : "weak";
}

// Ranks the uploaded resume against the curated role profiles. Runs before
// any analysis and never calls the LLM, so it is a few seconds at most; a
// plain busy state is enough here, unlike the full analysis.
export default function CareerFit({ file, onPick }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [forFile, setForFile] = useState(null);

  const stale = result && forFile !== file;

  async function run() {
    if (!file || loading) return;
    setError("");
    setLoading(true);
    try {
      const data = await suggestCareers(file);
      setResult(data);
      setForFile(file);
    } catch (err) {
      setError(messageForError(err));
    } finally {
      setLoading(false);
    }
  }

  if (!file) return null;

  return (
    <section className="career-fit" aria-live="polite">
      <div className="career-fit__head">
        <div>
          <h2>Career fit</h2>
          <p className="section-lead">
            Not sure what to target? Score this resume against typical postings for common
            roles and pick one to analyze.
          </p>
        </div>
        <button type="button" onClick={run} disabled={loading} className="button--secondary">
          {loading ? "Scoring…" : result && !stale ? "Rescore" : "Suggest roles"}
        </button>
      </div>

      {error && <p className="field-error">{error}</p>}

      {result && !stale && (
        <ol className="career-fit__list">
          {result.fits.slice(0, TOP_N).map((fit) => (
            <li key={fit.role} className="career-fit__item">
              <button
                type="button"
                className="career-fit__pick"
                onClick={() => onPick(fit.role)}
                title={`Use "${fit.role}" as the target role`}
              >
                <span className={`score-pill score-pill--${tone(fit.match_score)}`}>
                  {fit.match_score}%
                </span>
                <span className="career-fit__role">{fit.role}</span>
              </button>
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
      {result && !stale && (
        <p className="career-fit__foot">
          Top {TOP_N} of {result.profile_count} roles. Scores are the share of a typical
          posting&apos;s skills your resume already names, so a strong resume for a role
          usually lands between 50% and 80%.
        </p>
      )}
    </section>
  );
}
