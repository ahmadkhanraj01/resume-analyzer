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
  const [error, setError] = useState("");
  const [downloading, setDownloading] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    getReport(id)
      .then(setReport)
      .catch((err) => setError(messageForError(err)));
  }, [id]);

  async function handleDownload() {
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
      setError(messageForError(err));
    } finally {
      setDownloading(false);
    }
  }

  async function handleDelete() {
    if (!window.confirm("Delete this report? This cannot be undone.")) return;
    setDeleting(true);
    try {
      await deleteReport(id);
      navigate("/reports");
    } catch (err) {
      setError(messageForError(err));
      setDeleting(false);
    }
  }

  if (error) return <ErrorBanner message={error} />;
  if (!report) return <Spinner />;

  return (
    <div className="report-detail">
      <div className="report-detail__header">
        <h1>{report.title}</h1>
        <div className="report-detail__actions">
          <button type="button" onClick={handleDownload} disabled={downloading}>
            {downloading ? "Preparing PDF…" : "Download PDF"}
          </button>
          <button type="button" className="danger" onClick={handleDelete} disabled={deleting}>
            Delete
          </button>
        </div>
      </div>

      {/* Score first, then gaps, then questions, then the plan: users want
          the verdict before the detail. */}
      <ScoreRing score={report.match_score} />

      <section>
        <h2>Skill gaps</h2>
        <SkillGapList gaps={report.skill_gaps} />
      </section>

      <section>
        <h2>Technical questions</h2>
        {report.technical_qs.map((q, i) => (
          <QuestionCard key={i} {...q} />
        ))}
      </section>

      <section>
        <h2>Behavioral questions</h2>
        {report.behavioral_qs.map((q, i) => (
          <QuestionCard key={i} {...q} />
        ))}
      </section>

      <section>
        <h2>Preparation plan</h2>
        <PrepPlan days={report.preparation_plan} />
      </section>
    </div>
  );
}
