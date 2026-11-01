export function formatDate(isoString) {
  return new Date(isoString).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

// Several reports a day is the normal case, so the list needs the time too.
export function formatDateTime(isoString) {
  return new Date(isoString).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function scoreLabel(score) {
  if (score >= 85) return "Strong match";
  if (score >= 65) return "Good match";
  if (score >= 40) return "Partial match";
  return "Weak match";
}

export function severityLabel(severity) {
  return { critical: "Missing", moderate: "Partial", minor: "Covered" }[severity] || severity;
}
