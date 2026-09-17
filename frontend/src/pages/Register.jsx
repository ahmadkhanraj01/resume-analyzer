import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../context/useAuth";
import { messageForError, fieldErrorsForError } from "../lib/errorMessages";
import ErrorBanner from "../components/ErrorBanner";
import PasswordInput from "../components/PasswordInput";

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
      <div className="auth-card">
        <p className="auth-card__eyebrow">Get started</p>
        <h1>Create an account</h1>
        <p className="auth-card__lead">Free, and your reports stay private to you.</p>
        <ErrorBanner message={error} />
        <form onSubmit={handleSubmit} className="auth-form">
          <label htmlFor="register-email">
            Email
            <input
              id="register-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              placeholder="you@example.com"
            />
            {fieldErrors?.email && <span className="field-error">{fieldErrors.email}</span>}
          </label>
          <label htmlFor="register-password">
            Password
            <PasswordInput
              id="register-password"
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
            />
            {fieldErrors?.password ? (
              <span className="field-error">{fieldErrors.password}</span>
            ) : (
              <span className="field-hint">At least 8 characters.</span>
            )}
          </label>
          <button type="submit" className="btn-block" disabled={submitting}>
            {submitting ? "Creating account…" : "Create account"}
          </button>
        </form>
        <p className="auth-card__switch">
          Already have an account? <Link to="/login">Log in</Link>
        </p>
      </div>
    </div>
  );
}
