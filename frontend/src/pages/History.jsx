import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listReports } from "../api/interview";
import { messageForError } from "../lib/errorMessages";
import { formatDate, scoreLabel } from "../lib/format";
import Spinner from "../components/Spinner";
import ErrorBanner from "../components/ErrorBanner";

const PAGE_SIZE = 20;

export default function History() {
  const [items, setItems] = useState(null);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState("");
  const [loadingMore, setLoadingMore] = useState(false);

  useEffect(() => {
    listReports(PAGE_SIZE, 0)
      .then((data) => {
        setItems(data.items);
        setTotal(data.total);
      })
      .catch((err) => setError(messageForError(err)));
  }, []);

  async function loadMore() {
    setLoadingMore(true);
    setError("");
    try {
      const data = await listReports(PAGE_SIZE, items.length);
      setItems((prev) => [...prev, ...data.items]);
      setTotal(data.total);
    } catch (err) {
      setError(messageForError(err));
    } finally {
      setLoadingMore(false);
    }
  }

  if (items === null) {
    return error ? <ErrorBanner message={error} /> : <Spinner />;
  }

  const hasMore = items.length < total;

  return (
    <div className="history-page">
      <h1>Past reports</h1>
      <ErrorBanner message={error} />
      {items.length === 0 ? (
        <p>
          No reports yet. <Link to="/new">Start an analysis</Link>.
        </p>
      ) : (
        <>
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
          <p className="history-page__count">
            Showing {items.length} of {total}
          </p>
          {hasMore && (
            <button type="button" onClick={loadMore} disabled={loadingMore}>
              {loadingMore ? "Loading…" : "Load more"}
            </button>
          )}
        </>
      )}
    </div>
  );
}
