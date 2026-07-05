import { useEffect, useMemo, useState } from "react";

import { AppLayout } from "./components/layout";
import { ClientsPage } from "./pages/ClientsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ModelsPage } from "./pages/ModelsPage";
import { ProvidersPage } from "./pages/ProvidersPage";
import { RoutesPage } from "./pages/RoutesPage";
import { UsagePage } from "./pages/UsagePage";
import { LoginPage } from "./pages/LoginPage";
import { api, apiBase } from "./lib/api";
import { isKnownPath, tabFromPath, tabPaths } from "./lib/routes";
import type { Tab } from "./types/gateway";

export function App() {
  const [tab, setTab] = useState<Tab>(() => tabFromPath(window.location.pathname));
  const [adminToken, setAdminToken] = useState(localStorage.getItem("adminToken") || "");
  const [authenticated, setAuthenticated] = useState(Boolean(localStorage.getItem("adminToken")));
  const [notice, setNotice] = useState("");
  const headers = useMemo(
    () => ({ Authorization: `Bearer ${adminToken}`, "Content-Type": "application/json" }),
    [adminToken]
  );

  useEffect(() => {
    function syncTabWithLocation() {
      setTab(tabFromPath(window.location.pathname));
    }

    syncTabWithLocation();
    window.addEventListener("popstate", syncTabWithLocation);
    return () => window.removeEventListener("popstate", syncTabWithLocation);
  }, []);

  useEffect(() => {
    if (!isKnownPath(window.location.pathname) || window.location.pathname === "/") {
      window.history.replaceState(null, "", tabPaths.dashboard);
      setTab("dashboard");
    }
  }, []);

  useEffect(() => {
    if (authenticated && adminToken) {
      localStorage.setItem("adminToken", adminToken);
    }
  }, [adminToken, authenticated]);

  async function login({ adminToken, apiBaseUrl }: { adminToken: string; apiBaseUrl: string }) {
    localStorage.setItem("apiBase", apiBaseUrl);
    await api("/admin/dashboard", {
      headers: { Authorization: `Bearer ${adminToken}`, "Content-Type": "application/json" }
    }, setNotice);
    localStorage.setItem("adminToken", adminToken);
    setAdminToken(adminToken);
    setAuthenticated(true);
    setNotice(`Connected to ${apiBase()}`);
  }

  function navigate(path: string) {
    if (window.location.pathname !== path) {
      window.history.pushState(null, "", path);
    }
    setTab(tabFromPath(path));
  }

  function logout() {
    localStorage.removeItem("adminToken");
    setAdminToken("");
    setAuthenticated(false);
    setNotice("");
  }

  if (!authenticated) {
    return <LoginPage onLogin={login} />;
  }

  return (
    <AppLayout
      tab={tab}
      onNavigate={navigate}
      notice={notice}
      onLogout={logout}
    >
      {tab === "dashboard" && <DashboardPage headers={headers} setNotice={setNotice} />}
      {tab === "clients" && <ClientsPage headers={headers} setNotice={setNotice} />}
      {tab === "providers" && <ProvidersPage headers={headers} setNotice={setNotice} />}
      {tab === "models" && <ModelsPage headers={headers} setNotice={setNotice} />}
      {tab === "routes" && <RoutesPage headers={headers} setNotice={setNotice} />}
      {tab === "usage" && <UsagePage headers={headers} setNotice={setNotice} />}
    </AppLayout>
  );
}
