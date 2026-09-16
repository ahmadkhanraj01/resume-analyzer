import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import Spinner from "../components/Spinner";

export default function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();

  // Wait for the /auth/me hydration before deciding. Redirecting early
  // would flash the login page on every refresh of a protected route.
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}
