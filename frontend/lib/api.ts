const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const WA = process.env.NEXT_PUBLIC_WA_BRIDGE_URL || "http://localhost:3001";

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

export type Project = {
  id: string;
  name: string;
  description: string;
  chats: { id: string; title: string; chat_type: string; wa_jid?: string | null }[];
};

export type Directive = {
  id: string;
  natural_language: string;
  trigger: string;
  condition: Record<string, unknown>;
  action: Record<string, unknown>;
  enabled: boolean;
};

export type Persona = {
  id: string;
  participant: string;
  chat_id: string;
  project_id: string;
  profile: {
    name?: string;
    vocabulary?: string[];
    signature_phrases?: string[];
    emojis?: string[];
    active_hours?: number[];
    tone?: string;
    formality?: string;
    humor?: string;
    summary?: string;
  };
};

export type Alert = {
  id: string;
  summary: string;
  risk_level: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export const api = {
  health: () => req<{ ok: boolean }>("/api/health"),
  stats: () => req<Record<string, number | boolean>>("/api/stats"),
  projects: () => req<Project[]>("/api/projects"),
  createProject: (name: string, description = "") =>
    req("/api/projects", { method: "POST", body: JSON.stringify({ name, description }) }),
  createChat: (projectId: string, title: string, chat_type: "DIRECT" | "GROUP") =>
    req(`/api/projects/${projectId}/chats`, {
      method: "POST",
      body: JSON.stringify({ title, chat_type }),
    }),
  chat: (id: string) =>
    req<{
      id: string;
      project_id: string;
      title: string;
      chat_type: string;
      messages: { id: string; sender: string; body: string; ts: string }[];
    }>(`/api/chats/${id}`),
  parseDirective: (natural_language: string, project_id?: string) =>
    req<Directive>("/api/directives/parse", {
      method: "POST",
      body: JSON.stringify({ natural_language, project_id }),
    }),
  directives: () => req<Directive[]>("/api/directives"),
  toggleDirective: (id: string) => req<Directive>(`/api/directives/${id}/toggle`, { method: "POST" }),
  personas: (chatId?: string) =>
    req<Persona[]>(chatId ? `/api/personas?chat_id=${chatId}` : "/api/personas"),
  runAgent: (body: {
    project_id: string;
    chat_id: string;
    query: string;
    agent: string;
    participant?: string;
  }) => req<Record<string, unknown>>("/api/agents/run", { method: "POST", body: JSON.stringify(body) }),
  alerts: () => req<Alert[]>("/api/alerts/pending"),
  confirmAlert: (id: string) => req(`/api/alerts/${id}/confirm`, { method: "POST", body: "{}" }),
  rejectAlert: (id: string) => req(`/api/alerts/${id}/reject`, { method: "POST", body: "{}" }),
  focus: () => req<{ enabled: boolean }>("/api/focus-mode"),
  setFocus: (enabled: boolean) =>
    req("/api/focus-mode", { method: "POST", body: JSON.stringify({ enabled }) }),
  calendar: () => req<Record<string, unknown>>("/api/calendar"),
  uploadExport: async (project_id: string, chat_id: string, file: File) => {
    const fd = new FormData();
    fd.append("project_id", project_id);
    fd.append("chat_id", chat_id);
    fd.append("file", file);
    const res = await fetch(`${API}/api/ingest/upload`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
  waStatus: async () => {
    const res = await fetch(`${WA}/status`, { cache: "no-store" });
    if (!res.ok) throw new Error("bridge offline");
    return res.json() as Promise<{
      status: string;
      qr: string | null;
      lastError: string | null;
      directives: number;
      focusMode: boolean;
    }>;
  },
};

export { API };
