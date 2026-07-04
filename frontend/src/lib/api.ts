export function apiBase() {
  return localStorage.getItem("apiBase") || import.meta.env.VITE_API_BASE || "http://localhost:8004";
}

export async function api<T>(
  path: string,
  options: RequestInit,
  setNotice: (value: string) => void
): Promise<T> {
  const response = await fetch(`${apiBase()}${path}`, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("json") ? await response.json() : await response.text();
  if (!response.ok) {
    const message = typeof payload === "string" ? payload : payload.detail || "Request failed";
    setNotice(message);
    throw new Error(message);
  }
  return payload as T;
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
