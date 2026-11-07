"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Command" },
  { href: "/rules", label: "Directives" },
  { href: "/personas", label: "Personas" },
  { href: "/agents", label: "Agents" },
  { href: "/chats", label: "Memory" },
  { href: "/ingest", label: "Crafty Edge" },
];

export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="hidden w-60 shrink-0 border-r border-line bg-panel/60 p-5 md:flex md:flex-col">
      <div className="mb-8">
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-mint">hackathon</p>
        <h1 className="mt-1 text-xl font-bold tracking-tight">
          Agentic <span className="text-amber">Chase</span>
        </h1>
        <p className="mt-2 text-xs text-slate-400">Zero-leak memory. Prompt-to-action. HITL safety.</p>
      </div>
      <nav className="flex flex-col gap-1">
        {LINKS.map((l) => {
          const active = path === l.href;
          return (
            <Link
              key={l.href}
              href={l.href}
              className={`rounded-xl px-3 py-2 text-sm ${
                active ? "bg-amber/15 text-amber" : "text-slate-300 hover:bg-white/5"
              }`}
            >
              {l.label}
            </Link>
          );
        })}
      </nav>
      <p className="mt-auto pt-8 font-mono text-[10px] text-slate-500">localhost:3000 → :8000 → :3001</p>
    </aside>
  );
}
