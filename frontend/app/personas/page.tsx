"use client";

import { useEffect, useState } from "react";
import { api, type Persona, type Project } from "@/lib/api";

export default function PersonasPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [chatId, setChatId] = useState("");
  const [personas, setPersonas] = useState<Persona[]>([]);

  const chats = projects.flatMap((p) => p.chats.map((c) => ({ ...c, project: p.name })));

  async function load(id?: string) {
    const p = await api.projects();
    setProjects(p);
    const next = id || chatId || p[0]?.chats[0]?.id || "";
    if (!chatId && next) setChatId(next);
    setPersonas(await api.personas(next || undefined));
  }

  useEffect(() => {
    load().catch(console.error);
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-mint">dynamic profiling</p>
          <h2 className="mt-1 text-3xl font-bold">Persona viewer</h2>
        </div>
        <select
          className="max-w-sm"
          value={chatId}
          onChange={async (e) => {
            setChatId(e.target.value);
            setPersonas(await api.personas(e.target.value));
          }}
        >
          <option value="">All chats</option>
          {chats.map((c) => (
            <option key={c.id} value={c.id}>
              {c.project} / {c.title} ({c.chat_type})
            </option>
          ))}
        </select>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {personas.map((p) => (
          <article key={p.id} className="card p-5">
            <div className="flex items-center justify-between">
              <h3 className="text-xl font-semibold">{p.profile.name || p.participant}</h3>
              <span className="font-mono text-xs text-amber">{p.profile.tone || "tone n/a"}</span>
            </div>
            <p className="mt-2 text-sm text-slate-300">{p.profile.summary}</p>
            <p className="mt-3 text-xs uppercase tracking-wide text-slate-500">emojis</p>
            <p className="text-lg">{(p.profile.emojis || []).join(" ") || "—"}</p>
            <p className="mt-3 text-xs uppercase tracking-wide text-slate-500">vocabulary</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {(p.profile.vocabulary || []).map((w) => (
                <span key={w} className="rounded-full border border-line px-2 py-0.5 text-xs">
                  {w}
                </span>
              ))}
            </div>
            <p className="mt-3 text-xs uppercase tracking-wide text-slate-500">active hours</p>
            <p className="font-mono text-sm text-mint">{(p.profile.active_hours || []).join(", ") || "—"}</p>
            <p className="mt-2 text-xs text-slate-500">
              {p.profile.formality} · {p.profile.humor}
            </p>
          </article>
        ))}
        {!personas.length && <p className="text-sm text-slate-400">Ingest a chat export to extract personas.</p>}
      </div>
    </div>
  );
}
