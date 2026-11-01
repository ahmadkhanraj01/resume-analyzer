import { useState } from "react";

// Keywords are the job description's own wording, so copying them exactly
// is what gets them matched by applicant tracking systems.
function CopyButton({ text, label = "Copy" }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard access can be denied; the text is still on screen to select.
    }
  }

  return (
    <button type="button" className="button--secondary resume-tips__copy" onClick={copy}>
      {copied ? "Copied" : label}
    </button>
  );
}

export default function ResumeSuggestions({ id, keywords, rewrites }) {
  if (!keywords.length && !rewrites.length) return null;

  return (
    <section id={id} className="resume-tips">
      <h2>Resume edits</h2>
      <p className="section-lead">
        Changes that make this resume read closer to the job description. Only add what you can
        back up in an interview, and fill in any [placeholders] with real numbers.
      </p>

      {keywords.length > 0 && (
        <div className="resume-tips__block">
          <div className="resume-tips__block-head">
            <h3>Keywords to add</h3>
            <CopyButton text={keywords.join(", ")} label="Copy all" />
          </div>
          <ul className="resume-tips__keywords">
            {keywords.map((k) => (
              <li key={k}>{k}</li>
            ))}
          </ul>
        </div>
      )}

      {rewrites.length > 0 && (
        <div className="resume-tips__block">
          <h3>Suggested rewrites</h3>
          <ul className="resume-tips__rewrites">
            {rewrites.map((r, i) => (
              <li key={i} className="resume-tips__rewrite">
                <p className="resume-tips__before">
                  <span className="resume-tips__tag">Now</span>
                  <span>{r.original}</span>
                </p>
                <p className="resume-tips__after">
                  <span className="resume-tips__tag">Try</span>
                  <span>{r.improved}</span>
                  <CopyButton text={r.improved} />
                </p>
                <p className="resume-tips__reason">{r.reason}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
