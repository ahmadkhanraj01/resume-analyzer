import { severityLabel } from "../lib/format";

// critical (missing) first, then moderate (partial), then minor (covered).
// Users want to see what's wrong before what's fine.
const SEVERITY_ORDER = { critical: 0, moderate: 1, minor: 2 };

export default function SkillGapList({ gaps }) {
  const sorted = [...gaps].sort(
    (a, b) => SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity]
  );

  return (
    <ul className="skill-gap-list">
      {sorted.map((gap) => (
        <li key={gap.skill} className={`skill-gap skill-gap--${gap.severity}`}>
          <div className="skill-gap__header">
            <span className="skill-gap__badge">{severityLabel(gap.severity)}</span>
            <span className="skill-gap__name">{gap.skill}</span>
          </div>
          <p className="skill-gap__advice">{gap.advice}</p>
        </li>
      ))}
    </ul>
  );
}
