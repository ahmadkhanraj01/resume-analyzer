import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getReport, deleteReport, downloadReportPdf } from "../api/interview";
import { messageForError } from "../lib/errorMessages";
import ScoreRing from "../components/ScoreRing";
import SkillGapList from "../components/SkillGapList";
import QuestionCard from "../components/QuestionCard";
import PrepPlan from "../components/PrepPlan";
import Spinner from "../components/Spinner";
import ErrorBanner from "../components/ErrorBanner";

export default function ReportDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [report, setReport] = useState(null);
  // loadError replaces the page (there is nothing to show); actionError
  // sits above the report so a failed download or delete keeps it visible.
  const [loadError, setLoadError] = useState("");
  const [actionError, setActionError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  useEffect(() => {
    getReport(id)
      .then(setReport)
      .catch((err) => setLoadError(messageForError(err)));
  }, [id]);

  async function handleDownload() {
    setActionError("");
    setDownloading(true);
    try {
      const blob = await downloadReportPdf(id);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `report-${id}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setActionError(messageForError(err));
    } finally {
      setDownloading(false);
    }
  }

  async function handleDelete() {
    setActionError("");
    setDeleting(true);
    try {
      await deleteReport(id);
      navigate("/reports");
    } catch (err) {
      setActionError(messageForError(err));
      setDeleting(false);
      setConfirmingDelete(false);
    }
  }

  if (loadError) return <ErrorBanner message={loadError} />;
  if (!report) return <Spinner />;

  return (
    <div className="report-detail">
      <div className="report-detail__header">
        <h1>{report.title}</h1>
        <div className="report-detail__actions">
          <button type="button" onClick={handleDownload} disabled={downloading}>
            {downloading ? "Preparing PDF…" : "Download PDF"}
          </button>
          {confirmingDelete ? (
            <span className="confirm-inline" role="alertdialog" aria-label="Confirm delete">
              <span>Delete this report? This cannot be undone.</span>
              <button type="button" className="danger" onClick={handleDelete} disabled={deleting}>
                {deleting ? "Deleting…" : "Yes, delete"}
              </button>
              <button
                type="button"
                className="secondary"
                onClick={() => setConfirmingDelete(false)}
                disabled={deleting}
              >
                Cancel
              </button>
            </span>
          ) : (
            <button type="button" className="danger" onClick={() => setConfirmingDelete(true)}>
              Delete
            </button>
          )}
        </div>
      </div>

      <ErrorBanner message={actionError} />

      {/* Score first, then gaps, then questions, then the plan: users want
          the verdict before the detail. */}
      <ScoreRing score={report.match_score} />

      {report.scored_against === "role_profile" && (
        <div className="notice" role="note">
          <strong>Scored against a typical {report.role_title || "role"} profile.</strong> The text
          you entered named a role rather than a specific posting, so the skills below are the ones
          such jobs usually ask for. Paste a real job description for a score against that listing.
        </div>
      )}

      <section>
        <h2>Skill gaps</h2>
        <p className="section-lead">
          Skills the job description asks for that your resume does not clearly show, worst first.
        </p>
        <SkillGapList gaps={report.skill_gaps} />
      </section>

      <section>
        <h2>Technical questions</h2>
        <p className="section-lead">Answers are hidden so you can try each one first.</p>
        {report.technical_qs.map((q, i) => (
          <QuestionCard key={i} index={i} {...q} />
        ))}
      </section>

      <section>
        <h2>Behavioral questions</h2>
        {report.behavioral_qs.map((q, i) => (
          <QuestionCard key={i} index={i} {...q} />
        ))}
      </section>

      <section>
        <h2>Preparation plan</h2>
        <PrepPlan days={report.preparation_plan} />
      </section>
    </div>
  );
}
