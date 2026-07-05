import { Activity, Database, ListFilter, Route, ServerCog, ShieldCheck, Users } from "lucide-react";
import type React from "react";

import { tabPaths } from "../lib/routes";
import type { Tab } from "../types/gateway";

export const nav: Array<{ key: Tab; label: string; path: string; icon: React.ComponentType<{ size?: number }> }> = [
  { key: "dashboard", label: "Dashboard", path: tabPaths.dashboard, icon: Activity },
  { key: "clients", label: "Clients & Keys", path: tabPaths.clients, icon: Users },
  { key: "providers", label: "Providers", path: tabPaths.providers, icon: ServerCog },
  { key: "models", label: "Models & Aliases", path: tabPaths.models, icon: Database },
  { key: "routes", label: "Routes", path: tabPaths.routes, icon: Route },
  { key: "usage", label: "Usage Logs", path: tabPaths.usage, icon: ListFilter }
];

export function AppLayout({
  tab,
  onNavigate,
  adminToken,
  setAdminToken,
  notice,
  onLogout,
  children
}: {
  tab: Tab;
  onNavigate: (path: string) => void;
  adminToken: string;
  setAdminToken: (value: string) => void;
  notice: string;
  onLogout: () => void;
  children: React.ReactNode;
}) {
  return (
    <main className="min-h-screen bg-[#fbfcfb] text-ink">
      <aside className="fixed inset-y-0 left-0 w-68 border-r border-line bg-white px-4 py-5">
        <div className="mb-6 border-b border-line pb-4">
          <div className="flex items-center gap-2">
            <ShieldCheck size={22} className="text-accent" />
            <h1 className="text-lg font-semibold">LHQS AI Gateway</h1>
          </div>
          <p className="mt-2 text-sm text-slate-600">Operations console</p>
        </div>
        <nav className="space-y-1">
          {nav.map((item) => {
            const Icon = item.icon;
            return (
              <a
                key={item.key}
                href={item.path}
                onClick={(event) => {
                  if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
                    return;
                  }
                  event.preventDefault();
                  onNavigate(item.path);
                }}
                className={`flex h-10 w-full items-center gap-3 rounded-md px-3 text-sm ${
                  tab === item.key ? "bg-ink text-white" : "text-slate-700 hover:bg-panel"
                }`}
                aria-current={tab === item.key ? "page" : undefined}
              >
                <Icon size={17} />
                {item.label}
              </a>
            );
          })}
        </nav>
      </aside>

      <section className="ml-68 px-8 py-6">
        <header className="mb-6 flex items-center justify-between border-b border-line pb-4">
          <div>
            <h2 className="text-2xl font-semibold">{nav.find((item) => item.key === tab)?.label}</h2>
            <p className="mt-1 text-sm text-slate-600">Manage providers, routing, access, cache, failover, and logs.</p>
          </div>
          <div className="flex items-center gap-3">
            {notice && <span className="max-w-[360px] truncate text-sm text-slate-600">{notice}</span>}
            <input
              value={adminToken}
              onChange={(event) => setAdminToken(event.target.value)}
              placeholder="Admin bearer token"
              className="h-10 w-72 rounded-md border border-line bg-white px-3 text-sm outline-none focus:border-accent"
              type="password"
            />
            <button onClick={onLogout} className="h-10 rounded-md border border-line bg-white px-3 text-sm">
              Logout
            </button>
          </div>
        </header>
        {children}
      </section>
    </main>
  );
}
