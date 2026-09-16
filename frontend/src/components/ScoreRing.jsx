import { scoreLabel } from "../lib/format";

export default function ScoreRing({ score }) {
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - score / 100);

  return (
    <div className="score-ring">
      <svg viewBox="0 0 120 120" width="140" height="140">
        <circle cx="60" cy="60" r={radius} className="score-ring__track" />
        <circle
          cx="60"
          cy="60"
          r={radius}
          className="score-ring__fill"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform="rotate(-90 60 60)"
        />
        <text x="60" y="66" textAnchor="middle" className="score-ring__text">
          {score}%
        </text>
      </svg>
      <div className="score-ring__label">{scoreLabel(score)}</div>
    </div>
  );
}
