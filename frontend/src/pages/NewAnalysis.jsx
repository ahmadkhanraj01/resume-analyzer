import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { createReport } from "../api/interview";
import { messageForError } from "../lib/errorMessages";
import FileDrop from "../components/FileDrop";
import StagedProgress from "../components/StagedProgress";
import ErrorBanner from "../components/ErrorBanner";

const JD_MIN = 50;
const JD_MAX = 20000;
const SELF_MAX = 2000;

export default function NewAnalysis() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [jobDescription, setJobDescription] = useState("");
  const [selfDescription, setSelfDescription] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

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

  async function handleSubmit(e) {
    e.preventDefault();
    if (!canSubmit) return;
    setError("");
    setSubmitting(true);
    try {
      const report = await createReport({ resume: file, jobDescription, selfDescription });
      navigate(`/reports/${report.id}`);
    } catch (err) {
      setError(messageForError(err));
      setSubmitting(false);
    }
  }

  if (submitting) {
    return <StagedProgress />;
  }

  return (
    <div className="new-analysis-page">
      <h1>New analysis</h1>
      <ErrorBanner message={error} />
      <form onSubmit={handleSubmit} className="new-analysis-form">
        <label>Resume</label>
        <FileDrop file={file} onChange={setFile} onError={setError} />

        <label htmlFor="jd">
          Job description
          <textarea
            id="jd"
            required
            rows={10}
            maxLength={JD_MAX}
            value={jobDescription}
            onChange={(e) => setJobDescription(e.target.value)}
            placeholder="Paste the full job description here (at least 50 characters)."
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
