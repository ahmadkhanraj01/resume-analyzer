import { createContext, useContext, useEffect, useState, useCallback } from "react";
import * as authApi from "../api/auth";
import { getToken, setToken, setUnauthorizedHandler } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // Starts loading only if there's a token to hydrate; otherwise there is
  // nothing to wait for, computed here instead of via a synchronous
  // setState in the effect below.
  const [loading, setLoading] = useState(() => !!getToken());

  useEffect(() => {
    setUnauthorizedHandler(() => setUser(null));

    if (!getToken()) return;
    // Hydrate from /auth/me on mount. Routes must wait for `loading` to
    // settle before redirecting, otherwise a protected route flashes the
    // login page on every refresh while this request is in flight.
    authApi
      .me()
      .then(setUser)
      .catch(() => setToken(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email, password) => {
    const data = await authApi.login(email, password);
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  const register = useCallback(async (email, password) => {
    const data = await authApi.register(email, password);
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  const logout = useCallback(() => {
    // Logout is client-side token deletion. No server-side blacklist; see
    // ARCHITECTURE.md for why that trade-off is fine at this scale.
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
