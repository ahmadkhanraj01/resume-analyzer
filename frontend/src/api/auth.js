import client from "./client";

export function register(email, password) {
  return client.post("/auth/register", { email, password }).then((r) => r.data);
}

export function login(email, password) {
  return client.post("/auth/login", { email, password }).then((r) => r.data);
}

export function me() {
  return client.get("/auth/me").then((r) => r.data);
}
