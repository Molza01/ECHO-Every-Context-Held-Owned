import { create } from "zustand";
import type {
  AmbientUpdate,
  ContextEvent,
  IngestInfo,
  Phase,
  ProactiveSuggestion,
  SurfacedMemory,
  SystemStatus,
} from "@/types";
import { api, API_BASE } from "@/services/api";

interface RecentItem {
  id: string;
  preview: string;
  source_type: string;
  at: number;
}

export interface ActivitySignal {
  text: string;
  action?: string | null;
  kind?: string | null;
  name?: string | null;
  folder?: string | null;
  application?: string | null;
  at: number;
}

interface ContextState {
  status: SystemStatus | null;
  context: ContextEvent | null;
  surfaced: SurfacedMemory[];
  query: string | null;
  phase: Phase;
  detectedAt: number | null;
  lastIngest: IngestInfo | null;
  recent: RecentItem[];
  activitySignals: ActivitySignal[];
  suggestion: ProactiveSuggestion | null;
  wsConnected: boolean;
  dismissSuggestion: () => void;
  refreshStatus: () => Promise<void>;
  connect: () => void;
}

export const useContextStore = create<ContextState>((set, get) => {
  let ws: WebSocket | null = null;
  let retry: ReturnType<typeof setTimeout> | null = null;

  const applyUpdate = (u: AmbientUpdate, phase: Phase) =>
    set({
      context: u.context ?? get().context,
      surfaced: u.surfaced ?? [],
      query: u.query ?? get().query,
      phase,
    });

  const handle = (type: string, data: any) => {
    switch (type) {
      case "hello": {
        set({ phase: (data.phase as Phase) ?? "idle" });
        if (data.last_update) applyUpdate(data.last_update as AmbientUpdate, data.phase);
        else if (data.context) set({ context: data.context as ContextEvent });
        break;
      }
      case "context.updated":
        set({
          context: data.context as ContextEvent,
          phase: "detected",
          detectedAt: data.detected_at ?? Date.now(),
          surfaced: [],
          query: null,
        });
        break;
      case "retrieval.started":
        set({ phase: "checking", query: data.query ?? null });
        break;
      case "ambient.memory_found":
        applyUpdate(data as AmbientUpdate, "surfaced");
        break;
      case "retrieval.completed":
        applyUpdate(
          data as AmbientUpdate,
          (data.surfaced?.length ?? 0) > 0 ? "surfaced" : "none"
        );
        break;
      case "memory.ingested": {
        const info = data as IngestInfo;
        set({
          lastIngest: info,
          recent: [
            { id: info.id, preview: info.preview, source_type: info.source_type, at: Date.now() },
            ...get().recent,
          ].slice(0, 20),
        });
        break;
      }
      case "activity.signal": {
        const sig = data as ActivitySignal;
        if (sig.text)
          set({ activitySignals: [sig, ...get().activitySignals].slice(0, 40) });
        break;
      }
      case "proactive.suggestion":
        set({ suggestion: data as ProactiveSuggestion });
        break;
      case "source.status_changed":
      case "supermemory.status_changed":
        get().refreshStatus();
        break;
    }
  };

  const openSocket = () => {
    // dev: same-origin via Vite proxy; prod: the backend origin (API_BASE), http->ws
    const wsUrl = API_BASE
      ? `${API_BASE.replace(/^http/, "ws")}/ws`
      : `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;
    ws = new WebSocket(wsUrl);
    ws.onopen = () => set({ wsConnected: true });
    ws.onclose = () => {
      set({ wsConnected: false });
      if (retry) clearTimeout(retry);
      retry = setTimeout(openSocket, 2000);
    };
    ws.onerror = () => ws?.close();
    ws.onmessage = (evt) => {
      try {
        const msg = JSON.parse(evt.data);
        if (msg.type) handle(msg.type, msg.data ?? {});
      } catch {
        /* ignore malformed frames */
      }
    };
  };

  return {
    status: null,
    context: null,
    surfaced: [],
    query: null,
    phase: "idle",
    detectedAt: null,
    lastIngest: null,
    recent: [],
    activitySignals: [],
    suggestion: null,
    wsConnected: false,
    dismissSuggestion: () => set({ suggestion: null }),
    refreshStatus: async () => {
      try {
        set({ status: await api.status() });
      } catch {
        set({ status: null });
      }
    },
    connect: () => {
      if (ws) return;
      openSocket();
    },
  };
});
