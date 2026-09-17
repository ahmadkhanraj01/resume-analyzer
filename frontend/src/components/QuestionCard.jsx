import { useState } from "react";

// Answers collapse by default so the page is scannable and the user can
// self-test before revealing the model answer.
export default function QuestionCard({ question, intention, answer, index }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="question-card">
      <p className="question-card__question">
        {index != null && <span className="question-card__index">{index + 1}</span>}
        {question}
      </p>
      <p className="question-card__intention">Probing: {intention}</p>
      <button type="button" className="question-card__toggle" onClick={() => setOpen(!open)}>
        {open ? "Hide model answer" : "Show model answer"}
      </button>
      {open && (
        <div className="question-card__answer">
          <span className="question-card__answer-label">Model answer</span>
          <p>{answer}</p>
        </div>
      )}
    </div>
  );
}
