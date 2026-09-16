import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { messageForError, fieldErrorsForError } from "../lib/errorMessages";
import ErrorBanner from "../components/ErrorBanner";

export default function Register() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setFieldErrors(null);
    setSubmitting(true);
    try {
      // Register logs the user in directly; no separate login step.
      await register(email, password);
      navigate("/new");
    } catch (err) {
      setError(messageForError(err));
      setFieldErrors(fieldErrorsForError(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-page">
      <h1>Create an account</h1>
      <ErrorBanner message={error} />
      <form onSubmit={handleSubmit} className="auth-form">
        <label>
          Email
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="email"
          />
          {fieldErrors?.email && <span className="field-error">{fieldErrors.email}</span>}
        </label>
        <label>
          Password
          <input
            type="password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="new-password"
          />
          <span className="field-hint">At least 8 characters.</span>
        </label>
        <button type="submit" disabled={submitting}>
          {submitting ? "Creating account…" : "Create account"}
        </button>
      </form>
      <p>
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </div>
  );
}
