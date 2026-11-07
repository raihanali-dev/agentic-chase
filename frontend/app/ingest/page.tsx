"use client";

import { useEffect, useState } from "react";
import { api, type Project } from "@/lib/api";

export default function IngestPage() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [projectId, setProjectId] = useState("");
  const [chatId, setChatId] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<string>("");
  const [busy, setBusy] = useState(false);

  const project = projects.find((p) => p.id === projectId);

  useEffect(() => {
    api.projects().then((p) => {
      setProjects(p);
      if (p[0]) {
        setProjectId(p[0].id);
        setChatId(p[0].chats[0]?.id || "");
      }
    });
  }, []);

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.25em] text-mint">sponsor pipeline</p>
        <h2 className="mt-1 text-3xl font-bold">Crafty Edge ingest</h2>
        <p className="mt-2 text-sm text-slate-400">
          Upload a WhatsApp <code>.txt</code> export. The pipeline redacts PII, captions media, splits on 60+ minute
          gaps, and indexes chunks with project/chat metadata only.
        </p>
      </div>

      <form
        className="card space-y-4 p-5"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!file || !projectId || !chatId) return;
          setBusy(true);
          setResult("");
          try {
            const out = await api.uploadExport(projectId, chatId, file);
            setResult(JSON.stringify(out, null, 2));
          } catch (err) {
            setResult(String(err));
          } finally {
            setBusy(false);
          }
        }}
      >
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
        <input
          type="file"
          accept=".txt,text/plain"
          onChange={(e) => setFile(e.target.files?.[0] || null)}
        />
        <button className="btn-primary" disabled={busy || !file} type="submit">
          {busy ? "Indexing…" : "Run Crafty Edge"}
        </button>
      </form>

      {result && <pre className="card overflow-auto p-4 font-mono text-xs text-mint">{result}</pre>}
    </div>
  );
}
