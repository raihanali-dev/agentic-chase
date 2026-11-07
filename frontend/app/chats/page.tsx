"use client";

import { useEffect, useState } from "react";
import { api, type Project } from "@/lib/api";

export default function ChatsPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [chatId, setChatId] = useState("");
  const [detail, setDetail] = useState<{
    title: string;
    chat_type: string;
    project_id: string;
    messages: { id: string; sender: string; body: string; ts: string }[];
  } | null>(null);
  const [title, setTitle] = useState("");
  const [kind, setKind] = useState<"DIRECT" | "GROUP">("DIRECT");

  const chats = projects.flatMap((p) => p.chats.map((c) => ({ ...c, projectId: p.id, project: p.name })));

  async function loadProjects() {
    const p = await api.projects();
    setProjects(p);
    const first = p[0]?.chats[0]?.id;
    if (!chatId && first) {
      setChatId(first);
      setDetail(await api.chat(first));
    }
  }

  useEffect(() => {
    loadProjects().catch(console.error);
  }, []);

  return (
    <div className="space-y-6">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-mint">multi-tier isolation</p>
        <h2 className="mt-1 text-3xl font-bold">Chat memory</h2>
        <p className="mt-2 max-w-2xl text-sm text-slate-400">
          GROUP and DIRECT sit under a Project. Vector chunks are tagged with both IDs; agents cannot retrieve across
          chats.
        </p>
      </div>

      <form
        className="card flex flex-wrap items-end gap-3 p-4"
        onSubmit={async (e) => {
          e.preventDefault();
          const projectId = projects[0]?.id;
          if (!projectId || !title.trim()) return;
          await api.createChat(projectId, title.trim(), kind);
          setTitle("");
          await loadProjects();
        }}
      >
        <div className="min-w-[200px] flex-1">
          <label className="mb-1 block text-xs text-slate-400">New chat in first project</label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title" />
        </div>
        <select value={kind} onChange={(e) => setKind(e.target.value as "DIRECT" | "GROUP")} className="w-36">
          <option value="DIRECT">DIRECT</option>
          <option value="GROUP">GROUP</option>
        </select>
        <button className="btn-primary" type="submit">
          Add chat
        </button>
      </form>

      <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
        <div className="card divide-y divide-line overflow-hidden">
          {chats.map((c) => (
            <button
              key={c.id}
              className={`block w-full px-4 py-3 text-left text-sm ${chatId === c.id ? "bg-amber/10" : "hover:bg-white/5"}`}
              onClick={async () => {
                setChatId(c.id);
                setDetail(await api.chat(c.id));
              }}
            >
              <span className="font-medium">{c.title}</span>
              <span className="mt-1 block font-mono text-[10px] text-slate-500">
                {c.project} · {c.chat_type}
              </span>
            </button>
          ))}
        </div>
        <div className="card max-h-[70vh] overflow-auto p-4">
          {detail ? (
            <>
              <h3 className="font-semibold">
                {detail.title}{" "}
                <span className="font-mono text-xs text-mint">{detail.chat_type}</span>
              </h3>
              <ul className="mt-4 space-y-3">
                {detail.messages.map((m) => (
                  <li key={m.id} className="rounded-xl bg-ink px-3 py-2">
                    <p className="text-xs text-amber">
                      {m.sender} · {m.ts.replace("T", " ").slice(0, 16)}
                    </p>
                    <p className="mt-1 whitespace-pre-wrap text-sm">{m.body}</p>
                  </li>
                ))}
              </ul>
            </>
          ) : (
            <p className="text-sm text-slate-400">Select a chat.</p>
          )}
        </div>
      </div>
    </div>
  );
}
