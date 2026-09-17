import { useContext } from "react";
import { AuthContext } from "./context";

// Kept out of AuthContext.jsx so that file only exports a component, which
// is what React Fast Refresh needs to hot-reload it cleanly.
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
