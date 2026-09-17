import { useRef, useState } from "react";

const MAX_BYTES = 5 * 1024 * 1024;
const ACCEPTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
];

export default function FileDrop({ file, onChange, onError }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  function validateAndSet(candidate) {
    if (!candidate) return;
    // Client-side check only speeds up feedback; the server still validates
    // by magic bytes, since a renamed extension would sail past this.
    if (candidate.size > MAX_BYTES) {
      onError?.("That file is over the 5 MB limit.");
      return;
    }
    // Some browsers report an empty MIME type for .docx, so fall back to the
    // extension when type is blank. The server still checks magic bytes.
    const extOk = /\.(pdf|docx)$/i.test(candidate.name || "");
    const typeOk = candidate.type ? ACCEPTED_TYPES.includes(candidate.type) : extOk;
    if (!typeOk) {
      onError?.("Only PDF and DOCX files are supported.");
      return;
    }
    onChange(candidate);
  }

  return (
    <div
      className={`file-drop ${dragging ? "file-drop--dragging" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        validateAndSet(e.dataTransfer.files?.[0]);
      }}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.docx"
        hidden
        onChange={(e) => validateAndSet(e.target.files?.[0])}
      />
      <svg className="file-drop__icon" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
        <line x1="12" y1="18" x2="12" y2="12" />
        <polyline points="9 15 12 12 15 15" />
      </svg>
      {file ? (
        <>
          <span className="file-drop__filename">{file.name}</span>
          <span className="file-drop__sub">Click or drop to replace</span>
        </>
      ) : (
        <>
          <span className="file-drop__title">Drop your resume here, or click to browse</span>
          <span className="file-drop__sub">PDF or DOCX, up to 5 MB</span>
        </>
      )}
    </div>
  );
}
