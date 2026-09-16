import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listReports } from "../api/interview";
import { messageForError } from "../lib/errorMessages";
import { formatDate, scoreLabel } from "../lib/format";
import Spinner from "../components/Spinner";
import ErrorBanner from "../components/ErrorBanner";

export default function History() {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    listReports()
      .then((data) => setItems(data.items))
      .catch((err) => setError(messageForError(err)));
  }, []);

  if (error) return <ErrorBanner message={error} />;
  if (items === null) return <Spinner />;

  return (
    <div className="history-page">
      <h1>Past reports</h1>
      {items.length === 0 ? (
        <p>
          No reports yet. <Link to="/new">Start an analysis</Link>.
        </p>
      ) : (
        <ul className="history-list">
          {items.map((r) => (
            <li key={r.id} className="history-list__item">
              <Link to={`/reports/${r.id}`}>
                <span className="history-list__title">{r.title}</span>
                <span className="history-list__score">
                  {r.match_score}% &middot; {scoreLabel(r.match_score)}
                </span>
                <span className="history-list__date">{formatDate(r.created_at)}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
