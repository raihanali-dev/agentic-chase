"use client";

import { useEffect, useState } from "react";
import { api, type Project } from "@/lib/api";

const AGENTS = [
  { id: "analyze", label: "Deep Analyzer" },
  { id: "roast", label: "Persona Roaster" },
  { id: "reply", label: "Reply Giver" },
  { id: "stand_in", label: "Autonomous Stand-In" },
];

export default function AgentsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [chatId, setChatId] = useState("");
  const [agent, setAgent] = useState("analyze");
  const [query, setQuery] = useState("Summarize tension and unresolved threads in this chat.");
  const [out, setOut] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);

  const project = projects.find((p) => p.id === projectId);

  useEffect(() => {
    api.projects().then((p) => {
      setProjects(p);
      if (p[0]) {
        setProjectId(p[0].id);
        if (p[0].chats[0]) setChatId(p[0].chats[0].id);
      }
    });
  }, []);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-mint">langgraph</p>
        <h2 className="mt-1 text-3xl font-bold">Specialized agents</h2>
        <p className="mt-2 text-sm text-slate-400">
          Retrieval always filters Chroma by <code>project_id</code> + <code>chat_id</code>. High-risk intents pause
          for dashboard confirmation.
        </p>
      </div>

      <form
        className="card space-y-4 p-5"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            const result = await api.runAgent({
              project_id: projectId,
              chat_id: chatId,
              query,
              agent,
            });
            setOut(result);
          } catch (err) {
            setOut({ error: String(err) });
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="grid gap-3 sm:grid-cols-3">
          <select
            value={projectId}
            onChange={(e) => {
              setProjectId(e.target.value);
              const p = projects.find((x) => x.id === e.target.value);
              setChatId(p?.chats[0]?.id || "");
            }}
          >
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <select value={chatId} onChange={(e) => setChatId(e.target.value)}>
            {(project?.chats || []).map((c) => (
              <option key={c.id} value={c.id}>
                {c.title} ({c.chat_type})
              </option>
            ))}
          </select>
          <select value={agent} onChange={(e) => setAgent(e.target.value)}>
            {AGENTS.map((a) => (
              <option key={a.id} value={a.id}>
                {a.label}
              </option>
            ))}
          </select>
        </div>
        <textarea rows={3} value={query} onChange={(e) => setQuery(e.target.value)} />
        <button className="btn-primary" disabled={busy || !chatId} type="submit">
          {busy ? "Running graph…" : "Run agent"}
        </button>
      </form>

      {out && (
        <article className="card p-5">
          <p className="font-mono text-xs text-amber">
            risk={String(out.risk_level)} {out.requires_hitl ? "· PAUSED HITL" : ""}
          </p>
          <pre className="mt-3 whitespace-pre-wrap text-sm leading-relaxed text-slate-200">
            {String(out.result || "")}
          </pre>
          {Array.isArray(out.citations) && out.citations.length > 0 && (
            <div className="mt-4 space-y-2">
              <p className="text-xs uppercase tracking-wide text-slate-500">isolated citations</p>
              {(out.citations as { excerpt: string; start_ts?: string }[]).map((c, i) => (
                <p key={i} className="rounded-lg bg-ink p-2 font-mono text-xs text-mint">
                  [{i + 1}] {c.start_ts} — {c.excerpt}
                </p>
              ))}
            </div>
          )}
        </article>
      )}
    </div>
  );
}
