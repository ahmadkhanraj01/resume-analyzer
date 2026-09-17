import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createReport } from "../api/interview";
import { messageForError } from "../lib/errorMessages";
import FileDrop from "../components/FileDrop";
import StagedProgress from "../components/StagedProgress";
import ErrorBanner from "../components/ErrorBanner";
import CareerFit from "../components/CareerFit";

const JD_MIN = 10; // mirrors JD_MIN_LENGTH in backend/app/api/interview.py
const JD_MAX = 20000;
const SELF_MAX = 2000;

export default function NewAnalysis() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [jobDescription, setJobDescription] = useState("");
  const [selfDescription, setSelfDescription] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  // Set after a failed submit so the banner can offer a one-click retry
  // with the file and JD still in state instead of an empty-looking form.
  const [failed, setFailed] = useState(false);

  // Warn before unload while an analysis is in flight: the request can take
  // up to 25 seconds, and a refresh loses it entirely.
  useEffect(() => {
    if (!submitting) return;
    const handler = (e) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [submitting]);

  const jdTooShort = jobDescription.length > 0 && jobDescription.length < JD_MIN;
  const canSubmit = file && jobDescription.length >= JD_MIN && !submitting;

  async function submit() {
    if (!canSubmit) return;
    setError("");
    setFailed(false);
    setSubmitting(true);
    try {
      const report = await createReport({ resume: file, jobDescription, selfDescription });
      navigate(`/reports/${report.id}`);
    } catch (err) {
      setError(messageForError(err));
      setFailed(true);
      setSubmitting(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    submit();
  }

  if (submitting) {
    return <StagedProgress />;
  }

  return (
    <div className="new-analysis-page">
      <h1>New analysis</h1>
      <p className="page-lead">
        Upload your resume and paste the job description. You get a match score, the skills to
        close, likely interview questions, and a day-by-day plan.
      </p>
      <ErrorBanner message={error}>
        {failed && canSubmit && (
          <button type="button" className="error-banner__action" onClick={submit}>
            Try again
          </button>
        )}
      </ErrorBanner>
      <form onSubmit={handleSubmit} className="new-analysis-form card">
        <label>Resume</label>
        <FileDrop file={file} onChange={setFile} onError={setError} />

        <CareerFit
          file={file}
          onPick={(role) => {
            setJobDescription(`I want to be a ${role}.`);
            document.getElementById("jd")?.focus();
          }}
        />

        <label htmlFor="jd">
          Job description or target role
          <textarea
            id="jd"
            required
            rows={10}
            maxLength={JD_MAX}
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            placeholder="Paste the full job posting, requirements included. If you do not have one yet, describe the role you are targeting instead."
          />
          <span className="field-hint">
            {jobDescription.length}/{JD_MAX}
            {jdTooShort && ` — need at least ${JD_MIN} characters`}
          </span>
        </label>

        <label htmlFor="self">
          About you <span className="field-hint">(optional)</span>
          <textarea
            id="self"
            rows={4}
            maxLength={SELF_MAX}
            value={selfDescription}
            onChange={(e) => setSelfDescription(e.target.value)}
            placeholder="Anything you'd like the questions to take into account."
          />
        </label>

        <button type="submit" disabled={!canSubmit}>
          Analyze
        </button>
      </form>
    </div>
  );
}
