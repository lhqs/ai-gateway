import { Activity, Bot, Database, DollarSign, ListFilter, LogOut, PanelLeftClose, PanelLeftOpen, Route, ServerCog, Users } from "lucide-react";
import { useState } from "react";
import type React from "react";

import { tabPaths } from "../lib/routes";
import type { Tab } from "../types/gateway";

export const nav: Array<{ key: Tab; label: string; path: string; icon: React.ComponentType<{ size?: number }> }> = [
  { key: "dashboard", label: "Dashboard", path: tabPaths.dashboard, icon: Activity },
  { key: "workbench", label: "AI Workbench", path: tabPaths.workbench, icon: Bot },
  { key: "clients", label: "Clients & Keys", path: tabPaths.clients, icon: Users },
  { key: "providers", label: "Providers", path: tabPaths.providers, icon: ServerCog },
  { key: "models", label: "Models & Aliases", path: tabPaths.models, icon: Database },
  { key: "pricing", label: "Pricing", path: tabPaths.pricing, icon: DollarSign },
  { key: "routes", label: "Routes", path: tabPaths.routes, icon: Route },
  { key: "usage", label: "Usage Logs", path: tabPaths.usage, icon: ListFilter }
];

export function AppLayout({
  tab,
  onNavigate,
  notice,
  onLogout,
  children
}: {
  tab: Tab;
  onNavigate: (path: string) => void;
  notice: string;
  onLogout: () => void;
  children: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const sidebarWidth = collapsed ? "w-16" : "w-56";
  const contentMargin = collapsed ? "ml-16" : "ml-56";

  return (
    <main className="min-h-screen bg-[#fbfcfb] text-ink">
      <aside className={`fixed inset-y-0 left-0 flex ${sidebarWidth} flex-col border-r border-line bg-white transition-[width] duration-200`}>
        <div className="border-b border-line px-4 py-5">
          <div className="flex items-center gap-2">
            <img src="/favicon.svg" alt="" className="size-7 shrink-0" />
            {!collapsed && <h1 className="truncate text-base font-semibold">LHQS AI Gateway</h1>}
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto px-2 py-3">
          <ul className="space-y-0.5">
            {nav.map((item) => {
              const Icon = item.icon;
              return (
                <li key={item.key}>
                  <a
                    href={item.path}
                    onClick={(event) => {
                      if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) {
                        return;
                      }
                      event.preventDefault();
                      onNavigate(item.path);
                    }}
                    className={`flex h-9 w-full items-center gap-3 rounded-md px-3 text-sm transition-colors ${
                      tab === item.key
                        ? "bg-panel font-medium text-ink"
                        : "text-slate-600 hover:bg-panel/60 hover:text-ink"
                    } ${collapsed ? "justify-center px-0" : ""}`}
                    aria-current={tab === item.key ? "page" : undefined}
                    title={collapsed ? item.label : undefined}
                  >
                    <Icon size={16} />
                    {!collapsed && item.label}
                  </a>
                </li>
              );
            })}
          </ul>
        </nav>
        <div className="border-t border-line p-2">
          <button
            onClick={onLogout}
            className={`flex h-9 w-full items-center gap-3 rounded-md px-3 text-sm text-slate-600 transition-colors hover:bg-panel hover:text-ink ${collapsed ? "justify-center px-0" : ""}`}
            title={collapsed ? "Logout" : undefined}
          >
            <LogOut size={16} />
            {!collapsed && "Logout"}
          </button>
          <button
            onClick={() => setCollapsed((c) => !c)}
            className={`mt-1 flex h-9 w-full items-center gap-3 rounded-md px-3 text-sm text-slate-600 transition-colors hover:bg-panel hover:text-ink ${collapsed ? "justify-center px-0" : ""}`}
            title={collapsed ? "Expand" : "Collapse"}
          >
            {collapsed ? <PanelLeftOpen size={16} /> : <PanelLeftClose size={16} />}
            {!collapsed && "Collapse"}
          </button>
        </div>
      </aside>

      <section className={`${contentMargin} px-8 py-6 transition-[margin] duration-200`}>
        <header className="mb-6 flex items-center justify-between border-b border-line pb-4">
          <div>
            <h2 className="text-xl font-semibold tracking-tight">{nav.find((item) => item.key === tab)?.label}</h2>
            <p className="mt-0.5 text-sm text-slate-500">Manage providers, routing, access, cache, failover, and logs.</p>
          </div>
          {notice && (
            <span className="flex max-w-[280px] items-center gap-2 rounded-md bg-panel px-2.5 py-1.5 text-xs text-slate-600">
              <span className="size-1.5 shrink-0 rounded-full bg-emerald-500" />
              <span className="truncate">{notice}</span>
            </span>
          )}
        </header>
        {children}
      </section>
    </main>
  );
}
