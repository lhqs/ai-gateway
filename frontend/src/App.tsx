import { useEffect, useMemo, useState } from "react";

import { AppLayout } from "./components/layout";
import { ClientsPage } from "./pages/ClientsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ModelsPage } from "./pages/ModelsPage";
import { ProvidersPage } from "./pages/ProvidersPage";
import { RoutesPage } from "./pages/RoutesPage";
import { UsagePage } from "./pages/UsagePage";
import { LoginPage } from "./pages/LoginPage";
import type { Tab } from "./types/gateway";
import { api, apiBase } from "./lib/api";

export function App() {
  const [tab, setTab] = useState<Tab>("dashboard");
  const [adminToken, setAdminToken] = useState(localStorage.getItem("adminToken") || "");
  const [authenticated, setAuthenticated] = useState(Boolean(localStorage.getItem("adminToken")));
  const [notice, setNotice] = useState("");
  const headers = useMemo(
    () => ({ Authorization: `Bearer ${adminToken}`, "Content-Type": "application/json" }),
    [adminToken]
  );

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
      setTab={setTab}
      adminToken={adminToken}
      setAdminToken={setAdminToken}
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
