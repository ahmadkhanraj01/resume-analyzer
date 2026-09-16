// The only file that configures axios. Components never import axios
// directly: a component that did would silently skip the token attach and
// the 401 handling below.
import axios from "axios";

const TOKEN_KEY = "resume_analyzer_token";

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000/api",
});

client.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// A 401 means the token is gone or expired; clear it so the app falls back
// to the login page instead of retrying with a dead token forever.
let onUnauthorized = null;
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}

client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      setToken(null);
      onUnauthorized?.();
    }
    return Promise.reject(error);
  }
);

export default client;
