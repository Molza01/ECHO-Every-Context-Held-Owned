import type {
  Analytics,
  AskResponse,
  Diagnostics,
  GraphData,
  Memory,
  Passport,
  Profile,
  Session,
  SessionResume,
  SurfacedMemory,
  SystemStatus,
  WatchedLocations,
} from "@/types";

// Where the ECHO backend lives.
//  • dev  -> "" : requests are relative and go through the Vite proxy (unchanged)
//  • prod -> the visitor's OWN local backend at http://localhost:8765, or an explicit
//            VITE_API_URL (e.g. a tunnel) if you set one at build time on Vercel.
export const API_BASE = (
  import.meta.env.VITE_API_URL ?? (import.meta.env.PROD ? "http://localhost:8765" : "")
).replace(/\/$/, "");

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export const api = {
  status: () => req<SystemStatus>("/api/status"),
  diagnostics: () => req<Diagnostics>("/api/diagnostics"),
  currentContext: () =>
    req<{ context: unknown; last_update: unknown }>("/api/context/current"),
  search: (q: string, limit = 12) =>
    req<{ query: string; results: Memory[] }>("/api/search", {
      method: "POST",
      body: JSON.stringify({ q, limit }),
    }),
  memories: (limit = 100) =>
    req<{ memories: Memory[] }>(`/api/memories?limit=${limit}`),
  deleteMemory: (id: string) =>
    req<{ deleted: string }>(`/api/memories/${id}`, { method: "DELETE" }),
  updateMemory: (
    id: string,
    body: {
      content?: string;
      pinned?: boolean;
      important?: boolean;
      irrelevant?: boolean;
      note?: string;
    }
  ) =>
    req<{ updated: string }>(`/api/memories/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  ask: (question: string, history: { role: string; content: string }[] = []) =>
    req<AskResponse>("/api/ask", {
      method: "POST",
      body: JSON.stringify({ question, history }),
    }),
  sessions: () => req<{ sessions: Session[]; continue: Session[] }>("/api/sessions"),
  sessionDetail: (id: string) => req<Session & { memories: Memory[] }>(`/api/sessions/${id}`),
  renameSession: (id: string, title: string) =>
    req(`/api/sessions/${id}/rename`, { method: "POST", body: JSON.stringify({ title }) }),
  pinSession: (id: string, pinned: boolean) =>
    req(`/api/sessions/${id}/pin`, { method: "POST", body: JSON.stringify({ pinned }) }),
  passport: () => req<Passport>("/api/context/passport"),
  passportCorrect: (body: {
    goal?: string;
    task?: string;
    add_decision?: string;
    add_blocker?: string;
    remove?: string;
    pin?: string;
  }) =>
    req<Passport>("/api/context/passport/correct", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  passportExportUrl: (format: "markdown" | "json") =>
    `${API_BASE}/api/context/passport/export?format=${format}`,
  sessionResume: (id: string) => req<SessionResume>(`/api/sessions/${id}/resume`),
  profile: () => req<Profile>("/api/profile"),
  recentActivity: (limit = 30) =>
    req<{ items: Memory[] }>(`/api/activity/recent?limit=${limit}`),
  analytics: (period: "day" | "week" | "month") =>
    req<Analytics>(`/api/analytics?period=${period}`),
  reveal: (path: string) =>
    req<{ revealed: string }>("/api/activity/reveal", {
      method: "POST",
      body: JSON.stringify({ path }),
    }),
  locations: () => req<WatchedLocations>("/api/activity/locations"),
  manageLocation: (body: {
    action: "add" | "remove" | "exclude" | "pause" | "resume";
    path?: string;
    pattern?: string;
  }) =>
    req<WatchedLocations>("/api/activity/locations", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  timeline: (limit = 150) =>
    req<{ items: Memory[] }>(`/api/timeline?limit=${limit}`),
  graph: (limit = 120) => req<GraphData>(`/api/graph?limit=${limit}`),
  related: (body: {
    file_path?: string;
    project_name?: string;
    repository?: string;
    query?: string;
  }) =>
    req<{ query: string; surfaced: SurfacedMemory[] }>("/api/related", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  ingestManual: (content: string) =>
    req<{ accepted: boolean }>("/api/ingest", {
      method: "POST",
      body: JSON.stringify({ source_type: "manual", content, set_current: false }),
    }),
  importCommand: (body: {
    command: string;
    project_name?: string;
    repository?: string;
  }) =>
    req<{ remembered: string }>("/api/commands/import", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  toggleSource: (source: string, enabled: boolean) =>
    req<{ sources: Record<string, unknown> }>("/api/sources/toggle", {
      method: "POST",
      body: JSON.stringify({ source, enabled }),
    }),
  exportUrl: `${API_BASE}/api/export`,
};
