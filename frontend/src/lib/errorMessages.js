// One flat object keyed by the codes in DESIGN.md. Adding a backend error
// code means adding a line here in the same PR, otherwise users get the
// fallback message for a case that was specifically meant to be handled.
const ERROR_MESSAGES = {
  VALIDATION_ERROR: "Please check the form and try again.",
  INVALID_CREDENTIALS: "Incorrect email or password.",
  TOKEN_INVALID: "Your session has expired. Log in again.",
  NOT_FOUND: "That report could not be found.",
  FILE_TOO_LARGE: "That file is over the 5 MB limit. Try a smaller file.",
  UNSUPPORTED_FILE: "Only PDF and DOCX resumes are supported.",
  EXTRACTION_FAILED:
    "No readable text was found in that file. It looks like a scanned image; " +
    "upload a text-based PDF or DOCX instead.",
  LLM_UNAVAILABLE: "Analysis failed. Try again in a moment.",
  RATE_LIMITED: "You've hit the analysis limit for now. Try again later.",
};

const FALLBACK_MESSAGE = "Something went wrong. Try again.";

export function messageForError(error) {
  const code = error?.response?.data?.error?.code;
  return ERROR_MESSAGES[code] || FALLBACK_MESSAGE;
}

export function fieldErrorsForError(error) {
  return error?.response?.data?.error?.fields || null;
}
