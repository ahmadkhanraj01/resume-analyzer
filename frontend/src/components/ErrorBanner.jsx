export default function ErrorBanner({ message, children }) {
  if (!message) return null;
  return (
    <div className="error-banner" role="alert">
      <span>{message}</span>
      {children}
    </div>
  );
}
