"use client";

import { useEffect, useState } from "react";
import { API, api, type Alert } from "@/lib/api";

export function AlertDock() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [busy, setBusy] = useState<string | null>(null);

  async function load() {
    try {
      setAlerts(await api.alerts());
    } catch {
      /* backend booting */
    }
  }

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    let ws: WebSocket | null = null;
    try {
      ws = new WebSocket(API.replace("http", "ws") + "/ws/alerts");
      ws.onmessage = () => load();
    } catch {
      /* polling fallback */
    }
    return () => {
      clearInterval(t);
      ws?.close();
    };
  }, []);

  if (!alerts.length) return null;
  const a = alerts[0];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
      <div className="card max-w-lg w-full p-6">
        <p className="font-mono text-xs uppercase tracking-widest text-rose-400">human-in-the-loop</p>
        <h2 className="mt-2 text-xl font-semibold">Confirm high-risk action</h2>
        <p className="mt-2 text-sm text-slate-300">{a.summary}</p>
        <pre className="mt-4 max-h-40 overflow-auto rounded-xl bg-ink p-3 font-mono text-xs text-mint">
          {JSON.stringify(a.payload, null, 2)}
        </pre>
        <div className="mt-5 flex gap-3">
          <button
            className="btn-primary flex-1"
            disabled={busy === a.id}
            onClick={async () => {
              setBusy(a.id);
              await api.confirmAlert(a.id);
              setBusy(null);
              load();
            }}
          >
            Confirm & dispatch
          </button>
          <button
            className="btn-danger flex-1"
            disabled={busy === a.id}
            onClick={async () => {
              setBusy(a.id);
              await api.rejectAlert(a.id);
              setBusy(null);
              load();
            }}
          >
            Reject
          </button>
        </div>
      </div>
    </div>
  );
}
