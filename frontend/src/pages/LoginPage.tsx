import { ShieldCheck } from "lucide-react";
import { useState } from "react";

import { apiBase } from "../lib/api";

export function LoginPage({
  onLogin
}: {
  onLogin: (params: { adminToken: string; apiBaseUrl: string }) => Promise<void>;
}) {
  const [adminToken, setAdminToken] = useState(localStorage.getItem("adminToken") || "");
  const [apiBaseUrl, setApiBaseUrl] = useState(apiBase());
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError("");
    try {
      await onLogin({ adminToken, apiBaseUrl: apiBaseUrl.replace(/\/$/, "") });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-[#fbfcfb] px-6 text-ink">
      <section className="w-full max-w-md rounded-md border border-line bg-white">
        <div className="border-b border-line px-6 py-5">
          <div className="flex items-center gap-2">
            <ShieldCheck size={24} className="text-accent" />
            <h1 className="text-xl font-semibold">LHQS AI Gateway</h1>
          </div>
          <p className="mt-2 text-sm text-slate-600">Sign in with the backend admin token.</p>
        </div>
        <form onSubmit={submit} className="space-y-4 p-6">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-600">Backend URL</span>
            <input
              value={apiBaseUrl}
              onChange={(event) => setApiBaseUrl(event.target.value)}
              className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-accent"
              placeholder="http://localhost:8004"
              required
            />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-600">Admin Token</span>
            <input
              value={adminToken}
              onChange={(event) => setAdminToken(event.target.value)}
              className="h-10 w-full rounded-md border border-line px-3 text-sm outline-none focus:border-accent"
              type="password"
              placeholder="change-me-admin-token"
              required
            />
          </label>
          {error && <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</div>}
          <button className="h-10 w-full rounded-md bg-ink text-sm text-white" disabled={loading}>
            {loading ? "Checking..." : "Sign In"}
          </button>
        </form>
      </section>
    </main>
  );
}
