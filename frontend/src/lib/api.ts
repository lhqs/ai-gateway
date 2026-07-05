import type { AuthUser, TokenResponse } from "../types/gateway";

export function apiBase() {
  return import.meta.env.VITE_API_BASE || "http://localhost:8004";
}

export function authHeaders(accessToken = localStorage.getItem("accessToken") || "") {
  return { Authorization: `Bearer ${accessToken}`, "Content-Type": "application/json" };
}

export function saveAuth(payload: TokenResponse) {
  localStorage.setItem("accessToken", payload.access_token);
  localStorage.setItem("refreshToken", payload.refresh_token);
  localStorage.setItem("authUser", JSON.stringify(payload.user));
  localStorage.removeItem("adminToken");
  window.dispatchEvent(new CustomEvent("auth:updated", { detail: payload }));
}

export function clearAuth() {
  localStorage.removeItem("accessToken");
  localStorage.removeItem("refreshToken");
  localStorage.removeItem("authUser");
  localStorage.removeItem("adminToken");
  localStorage.removeItem("apiBase");
  window.dispatchEvent(new Event("auth:cleared"));
}

export function readAuthUser(): AuthUser | null {
  const value = localStorage.getItem("authUser");
  if (!value) return null;
  try {
    return JSON.parse(value) as AuthUser;
  } catch {
    localStorage.removeItem("authUser");
    return null;
  }
}

async function refreshAuthToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem("refreshToken");
  if (!refreshToken) return null;

  const response = await fetch(`${apiBase()}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken })
  });
  if (!response.ok) {
    clearAuth();
    return null;
  }

  const payload = (await response.json()) as TokenResponse;
  saveAuth(payload);
  return payload.access_token;
}

function withAccessToken(options: RequestInit, accessToken: string): RequestInit {
  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${accessToken}`);
  headers.set("Content-Type", headers.get("Content-Type") || "application/json");
  return { ...options, headers };
}

export async function api<T>(
  path: string,
  options: RequestInit,
  setNotice: (value: string) => void,
  allowRefresh = true
): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, options);
  const contentType = response.headers.get("content-type") || "";
  const text = await response.text();
  const payload = contentType.includes("json") && text ? JSON.parse(text) : text;
  if (!response.ok) {
    if (response.status === 401 && allowRefresh && !path.startsWith("/auth/")) {
      const accessToken = await refreshAuthToken();
      if (accessToken) {
        return api<T>(path, withAccessToken(options, accessToken), setNotice, false);
      }
    }
    const message = typeof payload === "string" ? payload : payload.detail || "Request failed";
    setNotice(message);
    throw new Error(message);
  }
  return payload as T;
}

export async function apiWithMeta<T>(
  path: string,
  options: RequestInit,
  setNotice: (value: string) => void
): Promise<{ data: T; total: number }> {
  const payload = await api<{ items: T; total: number }>(path, options, setNotice);
  return { data: payload.items, total: payload.total };
}

export function parseCsv(value: string) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

export function parseNumberCsv(value: string) {
  return parseCsv(value).map((item) => Number(item));
}

export function jsonPreview(value: unknown) {
  if (value === null || value === undefined) return "";
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}
