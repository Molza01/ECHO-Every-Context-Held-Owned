import { useState } from "react";
import { ArrowUpRight, Cloud, Database, Zap } from "lucide-react";
import { Card } from "@/components/ui";
import { cn } from "@/lib/utils";
import { useContextStore } from "@/stores/useContextStore";

const QUICKSTART = "https://supermemory.ai/docs/self-hosting/quickstart";

// editor syntax colors (fixed for the dark code panel, theme-independent)
const C = {
  cmt: "#5b6b82",
  kw: "#6ea8fe",
  str: "#f0a868",
  fn: "#d7dde8",
  punc: "#9aa6b6",
} as const;

type Tok = [string, keyof typeof C];
const CODE: Record<string, Tok[][]> = {
  TypeScript: [
    [["// 1 · start Supermemory Local", "cmt"]],
    [["//     runs privately at localhost:6767", "cmt"]],
    [["", "punc"]],
    [["const ", "kw"], ["res", "fn"], [" = ", "punc"], ["await ", "kw"], ["fetch", "fn"], ["(", "punc"]],
    [['  "http://localhost:6767/v3/health"', "str"]],
    [[");", "punc"]],
    [["// → { status: \"ok\" }  ✓ ECHO connects", "cmt"]],
  ],
  Python: [
    [["# 1 · start Supermemory Local (localhost:6767)", "cmt"]],
    [["import ", "kw"], ["httpx", "fn"]],
    [["", "punc"]],
    [["r = ", "punc"], ["httpx", "fn"], [".", "punc"], ["get", "fn"], ["(", "punc"]],
    [['  "http://localhost:6767/v3/health"', "str"]],
    [[")", "punc"]],
    [["# → {\"status\": \"ok\"}  ✓ ECHO connects", "cmt"]],
  ],
  cURL: [
    [["# check Supermemory Local is running", "cmt"]],
    [["curl ", "fn"], ["http://localhost:6767/v3/health", "str"]],
    [["", "punc"]],
    [["# → {\"status\":\"ok\"}  ✓ ECHO connects", "cmt"]],
  ],
};
const TABS = Object.keys(CODE);

/**
 * Shown ONLY when Supermemory Local is offline — prompts the user to connect the local
 * memory engine ECHO depends on. Hides itself when reachable (the sidebar dot conveys it).
 */
export function SupermemoryConnect() {
  const status = useContextStore((s) => s.status);
  const backendUp = useContextStore((s) => s.backendUp);
  const [tab, setTab] = useState("TypeScript");

  // Two "not fully connected" cases worth guiding the user through:
  const backendDown = backendUp === false;                       // can't reach the ECHO backend
  const memoryOffline = !!status && status.supermemory.reachable === false; // backend up, memory down
  if (!backendDown && !memoryOffline) return null;

  const lines = CODE[tab];

  return (
    <Card hover={false} className="mt-6 overflow-hidden">
      <div className="grid gap-0 lg:grid-cols-2">
        {/* ---------- left: connect copy + code editor ---------- */}
        <div className="border-b border-border p-6 lg:border-b-0 lg:border-r">
          <div className="mb-2 inline-flex items-center gap-2 rounded-full bg-warn/10 px-3 py-1 text-xs font-medium text-warn ring-1 ring-inset ring-warn/20">
            <span className="h-2 w-2 rounded-full bg-warn" />
            {backendDown ? "ECHO backend · not reachable" : "Supermemory · offline"}
          </div>
          <h3 className="font-display text-xl font-bold tracking-tight">
            {backendDown ? "Waking up ECHO" : "Connect ECHO to Supermemory"}
          </h3>
          <p className="mt-1.5 max-w-md text-sm leading-relaxed text-muted">
            {backendDown ? (
              <>
                ECHO can't reach its backend yet. If this is the hosted demo, the server may be
                waking up — it retries automatically, give it ~30s. Running it yourself? Start the
                local backend and it connects.
              </>
            ) : (
              <>
                ECHO remembers your work through <span className="text-text">Supermemory</span> — a
                memory engine (local at <span className="font-mono text-text">localhost:6767</span>,
                or Supermemory Cloud). It isn't connected yet. Start it and ECHO connects
                automatically.
              </>
            )}
          </p>

          {/* code editor mockup */}
          <div className="mt-4 overflow-hidden rounded-xl border border-black/20 bg-[#0d1322] shadow-lg">
            <div className="flex items-center gap-2 px-3.5 py-2.5">
              <span className="flex gap-1.5">
                <span className="h-3 w-3 rounded-full bg-[#ff5f57]" />
                <span className="h-3 w-3 rounded-full bg-[#febc2e]" />
                <span className="h-3 w-3 rounded-full bg-[#28c840]" />
              </span>
              <span className="ml-auto font-mono text-[11px] text-white/45">
                quickstart{tab === "Python" ? ".py" : tab === "cURL" ? ".sh" : ".ts"}
              </span>
            </div>
            <div className="flex border-b border-white/10 px-2 text-[12px]">
              {TABS.map((t) => (
                <button
                  key={t}
                  onClick={() => setTab(t)}
                  className={cn(
                    "relative px-3 py-2 font-medium transition-colors",
                    tab === t ? "text-white" : "text-white/45 hover:text-white/70"
                  )}
                >
                  {t}
                  {tab === t && <span className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-accent" />}
                </button>
              ))}
            </div>
            <div className="flex overflow-x-auto font-mono text-[12.5px] leading-[1.7]">
              <div className="select-none border-r border-white/5 px-3 py-3 text-right text-white/25">
                {lines.map((_, i) => (
                  <div key={i}>{i + 1}</div>
                ))}
              </div>
              <pre className="flex-1 px-4 py-3">
                {lines.map((line, i) => (
                  <div key={i} className="min-h-[1.7em] whitespace-pre">
                    {line.map(([text, kind], j) => (
                      <span key={j} style={{ color: C[kind] }}>{text}</span>
                    ))}
                  </div>
                ))}
              </pre>
            </div>
          </div>

          <a
            href={QUICKSTART}
            target="_blank"
            rel="noreferrer"
            className="press mt-4 inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white shadow-[0_2px_8px_rgba(47,91,255,0.25)] transition-all hover:bg-accent-soft hover:shadow-[0_4px_14px_rgba(47,91,255,0.32)]"
          >
            Get Started <ArrowUpRight size={16} />
          </a>
        </div>

        {/* ---------- right: animated on hover ---------- */}
        <div className="hero-glow group/sm relative flex flex-col justify-center gap-5 p-6">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
            {[
              { icon: Database, label: "Local storage", sub: "on your device" },
              { icon: Zap, label: "Fast recall", sub: "in milliseconds" },
              { icon: Cloud, label: "No cloud", sub: "private by default" },
            ].map((f, i) => (
              <div
                key={f.label}
                className="rounded-lg border border-border bg-panel p-3 text-center transition-all duration-300 group-hover/sm:-translate-y-1 group-hover/sm:border-accent/40 group-hover/sm:shadow-[0_8px_20px_rgba(47,91,255,0.10)]"
                style={{ transitionDelay: `${i * 60}ms` }}
              >
                <f.icon size={17} className="mx-auto mb-1.5 text-accent transition-transform duration-300 group-hover/sm:scale-110" />
                <div className="text-[12px] font-semibold text-text">{f.label}</div>
                <div className="text-[10.5px] text-muted">{f.sub}</div>
              </div>
            ))}
          </div>

          <div>
            <div className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-muted">
              Local recall
            </div>
            <div className="flex items-end gap-2.5" style={{ height: 76 }}>
              {[
                { h: 76, c: "#2f5bff" },
                { h: 48, c: "#7c3aed" },
                { h: 30, c: "#c599ff" },
              ].map((b, i) => (
                <div
                  key={i}
                  className="flex-1 origin-bottom rounded-t transition-transform duration-500 ease-out group-hover/sm:scale-y-110"
                  style={{ height: b.h, backgroundColor: b.c, transitionDelay: `${i * 90}ms` }}
                />
              ))}
            </div>
            <div className="mt-2 text-[11px] text-muted">Memories retrieved locally, on your machine.</div>
          </div>
        </div>
      </div>
    </Card>
  );
}
