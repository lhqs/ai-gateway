import type { Tab } from "../types/gateway";

export const tabPaths: Record<Tab, string> = {
  dashboard: "/dashboard",
  workbench: "/workbench",
  clients: "/clients",
  providers: "/providers",
  models: "/models",
  routes: "/routes",
  usage: "/usage"
};

const routeEntries = Object.entries(tabPaths) as Array<[Tab, string]>;

function normalizePath(pathname: string) {
  return pathname.replace(/\/+$/, "") || "/";
}

export function tabFromPath(pathname: string): Tab {
  const normalizedPath = normalizePath(pathname);
  if (normalizedPath === "/") {
    return "dashboard";
  }
  return routeEntries.find(([, path]) => path === normalizedPath)?.[0] || "dashboard";
}

export function isKnownPath(pathname: string) {
  const normalizedPath = normalizePath(pathname);
  return normalizedPath === "/" || routeEntries.some(([, path]) => path === normalizedPath);
}
