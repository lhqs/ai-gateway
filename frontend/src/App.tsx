import { useEffect, useMemo, useState } from "react";

import { AppLayout } from "./components/layout";
import { AuditLogsPage } from "./pages/AuditLogsPage";
import { ClientsPage } from "./pages/ClientsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { ModelsPage } from "./pages/ModelsPage";
import { PricingPage } from "./pages/PricingPage";
import { ProvidersPage } from "./pages/ProvidersPage";
import { RoutesPage } from "./pages/RoutesPage";
import { UsagePage } from "./pages/UsagePage";
import { LoginPage } from "./pages/LoginPage";
import { LandingPage } from "./pages/LandingPage";
import { WorkbenchPage } from "./pages/WorkbenchPage";
import { api, apiBase, authHeaders, clearAuth, readAuthUser, saveAuth } from "./lib/api";
import { isKnownPath, tabFromPath, tabPaths } from "./lib/routes";
import type { AuthUser, Tab, TokenResponse } from "./types/gateway";

export function App() {
  const [tab, setTab] = useState<Tab>(() => tabFromPath(window.location.pathname));
  const [pathname, setPathname] = useState(window.location.pathname);
  const [accessToken, setAccessToken] = useState(localStorage.getItem("accessToken") || "");
  const [currentUser, setCurrentUser] = useState<AuthUser | null>(() => readAuthUser());
  const [authenticated, setAuthenticated] = useState(Boolean(localStorage.getItem("accessToken")));
  const [notice, setNotice] = useState("");
  const headers = useMemo(() => authHeaders(accessToken), [accessToken]);

  useEffect(() => {
    function syncTabWithLocation() {
      setPathname(window.location.pathname);
      setTab(tabFromPath(window.location.pathname));
    }

    syncTabWithLocation();
    window.addEventListener("popstate", syncTabWithLocation);
    return () => window.removeEventListener("popstate", syncTabWithLocation);
  }, []);

  useEffect(() => {
    if (!isKnownPath(window.location.pathname) && window.location.pathname !== "/login") {
      window.history.replaceState(null, "", "/");
      setPathname("/");
    }
  }, []);

  useEffect(() => {
    const isProtectedPath = pathname !== "/" && isKnownPath(pathname);
    if (!authenticated && isProtectedPath) {
      window.history.replaceState(null, "", "/login");
      setPathname("/login");
    } else if (authenticated && pathname === "/login") {
      window.history.replaceState(null, "", tabPaths.dashboard);
      setPathname(tabPaths.dashboard);
      setTab("dashboard");
    }
  }, [authenticated, pathname]);

  useEffect(() => {
    function handleAuthUpdated(event: Event) {
      const detail = (event as CustomEvent<TokenResponse>).detail;
      setAccessToken(detail.access_token);
      setCurrentUser(detail.user);
      setAuthenticated(true);
    }

    function handleAuthCleared() {
      setAccessToken("");
      setCurrentUser(null);
      setAuthenticated(false);
    }

    window.addEventListener("auth:updated", handleAuthUpdated);
    window.addEventListener("auth:cleared", handleAuthCleared);
    return () => {
      window.removeEventListener("auth:updated", handleAuthUpdated);
      window.removeEventListener("auth:cleared", handleAuthCleared);
    };
  }, []);

  async function login({
    account,
    password
  }: {
    account: string;
    password: string;
  }) {
    const payload = await api<TokenResponse>(
      "/auth/login",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ account, password })
      },
      setNotice,
      false
    );
    saveAuth(payload);
    setAccessToken(payload.access_token);
    setCurrentUser(payload.user);
    setAuthenticated(true);
    setNotice(`Connected to ${apiBase()}`);
    window.history.replaceState(null, "", tabPaths.dashboard);
    setPathname(tabPaths.dashboard);
    setTab("dashboard");
  }

  function navigate(path: string) {
    if (window.location.pathname !== path) {
      window.history.pushState(null, "", path);
    }
    setPathname(path);
    setTab(tabFromPath(path));
  }

  async function logout() {
    const refreshToken = localStorage.getItem("refreshToken");
    if (refreshToken && accessToken) {
      try {
        await api<unknown>(
          "/auth/logout",
          {
            method: "POST",
            headers,
            body: JSON.stringify({ refresh_token: refreshToken })
          },
          setNotice,
          false
        );
      } catch {
        // Local logout should still complete if the session is already expired server-side.
      }
    }
    clearAuth();
    setNotice("");
    window.history.replaceState(null, "", "/login");
    setPathname("/login");
  }

  if (pathname === "/") {
    return <LandingPage />;
  }

  if (!authenticated) {
    return <LoginPage onLogin={login} />;
  }

  return (
    <AppLayout
      tab={tab}
      onNavigate={navigate}
      notice={notice || (currentUser ? currentUser.username : "")}
      onLogout={logout}
    >
      {tab === "dashboard" && <DashboardPage headers={headers} setNotice={setNotice} />}
      {tab === "workbench" && <WorkbenchPage headers={headers} setNotice={setNotice} />}
      {tab === "clients" && <ClientsPage headers={headers} setNotice={setNotice} />}
      {tab === "providers" && <ProvidersPage headers={headers} setNotice={setNotice} />}
      {tab === "models" && <ModelsPage headers={headers} setNotice={setNotice} />}
      {tab === "pricing" && <PricingPage headers={headers} setNotice={setNotice} />}
      {tab === "routes" && <RoutesPage headers={headers} setNotice={setNotice} />}
      {tab === "usage" && <UsagePage headers={headers} setNotice={setNotice} />}
      {tab === "audit" && <AuditLogsPage headers={headers} setNotice={setNotice} />}
    </AppLayout>
  );
}
