"use client";

import { useEffect, useState } from "react";
import { api, type Project } from "@/lib/api";

export default function CommandCenter() {
  const [stats, setStats] = useState<Record<string, number | boolean> | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [wa, setWa] = useState<{ status: string; qr: string | null; lastError: string | null } | null>(null);
  const [focus, setFocus] = useState(false);
  const [calendar, setCalendar] = useState<Record<string, unknown> | null>(null);
  const [newName, setNewName] = useState("");

  async function refresh() {
    try {
      const [s, p, f, c] = await Promise.all([api.stats(), api.projects(), api.focus(), api.calendar()]);
      setStats(s);
      setProjects(p);
      setFocus(f.enabled);
      setCalendar(c);
    } catch {
      /* still starting */
    }
    try {
      setWa(await api.waStatus());
    } catch {
      setWa({ status: "bridge offline", qr: null, lastError: "start wa-bridge" });
    }
  }

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, []);

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.25em] text-mint">command center</p>
          <h2 className="mt-1 text-3xl font-bold">Chase the signal, not the noise.</h2>
        </div>
        <button
          className={focus ? "btn-primary" : "btn-ghost"}
          onClick={async () => {
            await api.setFocus(!focus);
            setFocus(!focus);
          }}
        >
          Focus Mode {focus ? "ON" : "OFF"}
        </button>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          ["Projects", stats?.projects ?? "—"],
          ["Chats", stats?.chats ?? "—"],
          ["Indexed msgs", stats?.messages ?? "—"],
          ["HITL paused", stats?.pending_alerts ?? "—"],
        ].map(([k, v]) => (
          <div key={String(k)} className="card p-4">
            <p className="text-xs uppercase tracking-wider text-slate-400">{k}</p>
            <p className="mt-2 text-3xl font-semibold text-amber">{String(v)}</p>
          </div>
        ))}
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="card p-5">
          <h3 className="text-lg font-semibold">WhatsApp bridge</h3>
          <p className="mt-1 text-sm text-slate-400">
            Status: <span className="text-mint">{wa?.status || "unknown"}</span>
          </p>
          {wa?.lastError && <p className="mt-2 text-xs text-rose-300">{wa.lastError}</p>}
          {wa?.qr && (
            <div className="mt-4">
              <p className="mb-2 text-sm">Scan this QR with WhatsApp → Linked devices.</p>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={wa.qr} alt="WhatsApp QR" className="w-56 rounded-xl border border-line" />
            </div>
          )}
          {wa?.status === "connected" && (
            <p className="mt-3 text-sm text-mint">Live. Call offers and messages are bound to directives.</p>
          )}
        </div>

        <div className="card p-5">
          <h3 className="text-lg font-semibold">Stand-in calendar</h3>
          <p className="mt-1 text-xs text-slate-400">{String(calendar?.source || "mock")} · {String(calendar?.timezone || "")}</p>
          <p className="mt-3 text-sm">
            Now: {calendar?.is_busy ? <span className="text-amber">BUSY</span> : <span className="text-mint">FREE</span>}
          </p>
          <ul className="mt-3 space-y-2 text-sm">
            {((calendar?.events as { title: string; start: string; end: string }[]) || []).map((e) => (
              <li key={e.title + e.start} className="rounded-lg border border-line px-3 py-2">
                <span className="text-slate-200">{e.title}</span>
                <span className="ml-2 font-mono text-xs text-slate-500">
                  {e.start?.slice(11, 16)}–{e.end?.slice(11, 16)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <section className="card p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-lg font-semibold">Projects (context isolation roots)</h3>
          <form
            className="flex gap-2"
            onSubmit={async (e) => {
              e.preventDefault();
              if (!newName.trim()) return;
              await api.createProject(newName.trim());
              setNewName("");
              refresh();
            }}
          >
            <input value={newName} onChange={(e) => setNewName(e.target.value)} placeholder="New project name" />
            <button className="btn-primary whitespace-nowrap" type="submit">
              Create
            </button>
          </form>
        </div>
        <div className="mt-4 grid gap-3 md:grid-cols-2">
          {projects.map((p) => (
            <div key={p.id} className="rounded-xl border border-line p-4">
              <p className="font-semibold">{p.name}</p>
              <p className="text-xs text-slate-400">{p.description}</p>
              <ul className="mt-3 space-y-1 text-sm">
                {p.chats.map((c) => (
                  <li key={c.id} className="flex justify-between">
                    <span>{c.title}</span>
                    <span className="font-mono text-xs text-mint">{c.chat_type}</span>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
