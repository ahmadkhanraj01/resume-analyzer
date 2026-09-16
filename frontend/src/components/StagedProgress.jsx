import { useEffect, useState } from "react";

// Driven by elapsed time, not real callbacks: the backend call is one
// synchronous request with no progress events. This is honest about the
// pipeline order even though it isn't wired to actual server-side stages;
// see DESIGN.md's "the waiting problem".
const STAGES = [
  { at: 0, label: "Reading your resume" },
  { at: 3000, label: "Matching skills against the role" },
  { at: 8000, label: "Generating interview questions" },
  { at: 18000, label: "Building your preparation plan" },
];

export default function StagedProgress() {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const id = setInterval(() => setElapsed(Date.now() - start), 250);
    return () => clearInterval(id);
  }, []);

  const current = [...STAGES].reverse().find((s) => elapsed >= s.at) || STAGES[0];

  return (
    <div className="staged-progress">
      <div className="staged-progress__spinner" />
      <p className="staged-progress__label">{current.label}&hellip;</p>
      <p className="staged-progress__hint">
        This can take up to 25 seconds, longer if the server just woke up.
      </p>
    </div>
  );
}
