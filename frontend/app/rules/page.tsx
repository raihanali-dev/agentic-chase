"use client";

import { useEffect, useState } from "react";
import { api, type Directive, type Project } from "@/lib/api";

const EXAMPLE = "If anyone WhatsApp calls me after 8 PM, reject it and text them 'I am offline for the day.'";

export default function RulesPage() {
  const [text, setText] = useState(EXAMPLE);
  const [projectId, setProjectId] = useState("");
  const [projects, setProjects] = useState<Project[]>([]);
  const [rules, setRules] = useState<Directive[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function load() {
    const [p, d] = await Promise.all([api.projects(), api.directives()]);
    setProjects(p);
    setRules(d);
    if (!projectId && p[0]) setProjectId(p[0].id);
  }

  useEffect(() => {
    load().catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-mint">prompt-to-action</p>
        <h2 className="mt-1 text-3xl font-bold">Directive creator</h2>
        <p className="mt-2 text-sm text-slate-400">
          Gemini parses natural language into Trigger / Condition / Action JSON. The Node bridge executes matching
          events instantly — no LangGraph round-trip.
        </p>
      </div>

      <form
        className="card space-y-4 p-5"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            await api.parseDirective(text, projectId || undefined);
            setText("");
            await load();
          } catch (err) {
            setError(String(err));
          } finally {
            setBusy(false);
          }
        }}
      >
        <textarea rows={4} value={text} onChange={(e) => setText(e.target.value)} />
        <div className="flex flex-wrap gap-3">
          <select value={projectId} onChange={(e) => setProjectId(e.target.value)} className="max-w-xs">
            {projects.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <button className="btn-primary" disabled={busy || !text.trim()} type="submit">
            {busy ? "Parsing…" : "Compile directive"}
          </button>
        </div>
        {error && <p className="text-sm text-rose-300">{error}</p>}
      </form>

      <div className="space-y-3">
        {rules.map((r) => (
          <article key={r.id} className="card p-4">
            <div className="flex items-start justify-between gap-3">
              <p className="text-sm text-slate-200">{r.natural_language}</p>
              <button className="btn-ghost text-xs" onClick={() => api.toggleDirective(r.id).then(load)}>
                {r.enabled ? "Enabled" : "Disabled"}
              </button>
            </div>
            <div className="mt-3 grid gap-2 font-mono text-xs text-mint sm:grid-cols-3">
              <div className="rounded-lg bg-ink p-2">trigger: {r.trigger}</div>
              <div className="rounded-lg bg-ink p-2">cond: {JSON.stringify(r.condition)}</div>
              <div className="rounded-lg bg-ink p-2">action: {JSON.stringify(r.action)}</div>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
