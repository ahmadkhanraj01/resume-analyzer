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
      {file ? (
        <span className="file-drop__filename">{file.name}</span>
      ) : (
        <span>Drag a resume here, or click to choose a PDF or DOCX (max 5 MB)</span>
      )}
    </div>
  );
}
