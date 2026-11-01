import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getReport, deleteReport, downloadReportPdf } from "../api/interview";
import { messageForError } from "../lib/errorMessages";
import { formatDateTime } from "../lib/format";
import ScoreTape from "../components/ScoreTape";
import SkillGapList from "../components/SkillGapList";
import QuestionCard from "../components/QuestionCard";
import PrepPlan from "../components/PrepPlan";
import ResumeSuggestions from "../components/ResumeSuggestions";
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

  const keywords = report.resume_keywords ?? [];
  const rewrites = report.resume_rewrites ?? [];
  // Only sections with content get a rail link, so the rail never points
  // at something that is not on the page.
  const sections = [
    { id: "gaps", label: "Skill gaps", count: report.skill_gaps.length },
    { id: "resume", label: "Resume edits", count: keywords.length + rewrites.length },
    { id: "technical", label: "Technical questions", count: report.technical_qs.length },
    { id: "behavioral", label: "Behavioral questions", count: report.behavioral_qs.length },
    { id: "plan", label: "Preparation plan", count: report.preparation_plan.length },
  ].filter((s) => s.count > 0);

  return (
    <div className="report-detail">
      <header className="report-detail__header">
        <div className="report-detail__heading">
          <h1>{report.title}</h1>
          <p className="report-detail__meta">
            {report.resume_filename && <>{report.resume_filename}, </>}
            {formatDateTime(report.created_at)}
          </p>
        </div>
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
      </header>

      <ErrorBanner message={actionError} />

      {/* Score first, then gaps and resume fixes, then questions, then the
          plan: users want the verdict before the detail. */}
      <ScoreTape score={report.match_score} />

      {report.scored_against === "role_profile" && (
        <div className="notice" role="note">
          <strong>Scored against a typical {report.role_title || "role"} profile.</strong> The text
          you entered named a role rather than a specific posting, so the skills below are the ones
          such jobs usually ask for. Paste a real job description for a score against that listing.
        </div>
      )}

      <div className="report-detail__layout">
        <nav className="report-rail" aria-label="Report sections">
          <ol>
            {sections.map((s) => (
              <li key={s.id}>
                <a href={`#${s.id}`}>
                  <span>{s.label}</span>
                  <span className="report-rail__count">{s.count}</span>
                </a>
              </li>
            ))}
          </ol>
        </nav>

        <div className="report-detail__body">
          {report.skill_gaps.length > 0 && (
            <section id="gaps">
              <h2>Skill gaps</h2>
              <p className="section-lead">
                Skills the job asks for that your resume does not clearly show, worst first.
              </p>
              <SkillGapList gaps={report.skill_gaps} />
            </section>
          )}

          <ResumeSuggestions id="resume" keywords={keywords} rewrites={rewrites} />

          <section id="technical">
            <h2>Technical questions</h2>
            <p className="section-lead">Answers are hidden so you can try each one first.</p>
            {report.technical_qs.map((q, i) => (
              <QuestionCard key={i} index={i} {...q} />
            ))}
          </section>

          <section id="behavioral">
            <h2>Behavioral questions</h2>
            {report.behavioral_qs.map((q, i) => (
              <QuestionCard key={i} index={i} {...q} />
            ))}
          </section>

          <section id="plan">
            <h2>Preparation plan</h2>
            <PrepPlan days={report.preparation_plan} />
          </section>
        </div>
      </div>
    </div>
  );
}
