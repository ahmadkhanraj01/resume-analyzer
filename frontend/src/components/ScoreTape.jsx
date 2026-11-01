import { scoreLabel } from "../lib/format";

const MAJOR_TICKS = [0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100];

// The match score drawn as a tailor's tape measure: how much of the job
// your resume already fits. The pin slides in once on load, the only
// ambient motion on the page.
export default function ScoreTape({ score }) {
  const tone = score >= 65 ? "good" : score >= 40 ? "partial" : "weak";

  return (
    <figure className={`score-tape score-tape--${tone}`} style={{ "--score": score }}>
      <figcaption className="score-tape__readout">
        <span className="score-tape__value">{score}%</span>
        <span className="score-tape__label">{scoreLabel(score)}</span>
      </figcaption>

      <div
        className="score-tape__tape"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={score}
        aria-label="Match score"
      >
        <div className="score-tape__rest" />
        <div className="score-tape__pin" aria-hidden="true" />
        {MAJOR_TICKS.map((t) => (
          <span key={t} className="score-tape__num" style={{ "--at": t }} aria-hidden="true">
            {t}
          </span>
        ))}
      </div>

      <p className="score-tape__caption">
        Share of the job&apos;s skills your resume already shows. The same resume and posting
        always get the same score.
      </p>
    </figure>
  );
}
