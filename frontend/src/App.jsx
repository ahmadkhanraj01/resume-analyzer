import { Routes, Route, Navigate, Link } from "react-router-dom";
import { useAuth } from "./context/useAuth";
import ProtectedRoute from "./routes/ProtectedRoute";
import Login from "./pages/Login";
import Register from "./pages/Register";
import NewAnalysis from "./pages/NewAnalysis";
import History from "./pages/History";
import ReportDetail from "./pages/ReportDetail";

function NavBar() {
  const { user, logout } = useAuth();
  if (!user) return null;
  return (
    <nav className="nav-bar">
      <Link to="/new" className="nav-bar__brand">
        Resume Analyzer
      </Link>
      <div className="nav-bar__links">
        <Link to="/new">New analysis</Link>
        <Link to="/reports">History</Link>
        <button type="button" onClick={logout}>
          Log out
        </button>
      </div>
    </nav>
  );
}

function NotFound() {
  return (
    <div className="not-found">
      <h1>Page not found</h1>
      <p>
        That address does not exist. <Link to="/">Go home</Link>.
      </p>
    </div>
  );
}

function Home() {
  const { user, loading } = useAuth();
  if (loading) return null;
  return <Navigate to={user ? "/new" : "/login"} replace />;
}

export default function App() {
  return (
    <>
      <NavBar />
      <main className="app-main">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route
            path="/new"
            element={
              <ProtectedRoute>
                <NewAnalysis />
              </ProtectedRoute>
            }
          />
          <Route
            path="/reports"
            element={
              <ProtectedRoute>
                <History />
              </ProtectedRoute>
            }
          />
          <Route
            path="/reports/:id"
            element={
              <ProtectedRoute>
                <ReportDetail />
              </ProtectedRoute>
            }
          />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
    </>
  );
}
