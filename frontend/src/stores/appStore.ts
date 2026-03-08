import { create } from "zustand";
import type { Conversation, ChatMessage, AOI, WsEvent } from "../types";
import { api } from "../lib/api";

export interface ToolEvent {
  tool: string;
  status: "running" | "done";
  output?: string;
  imagery_files?: string[];
}

export type StreamElement =
  | { kind: "text"; content: string }
  | { kind: "tool"; event: ToolEvent };

interface StreamingMessage {
  elements: StreamElement[];
  imagery_files: string[];
}

export interface OverlayImage {
  filename: string;
  bounds: [number, number, number, number]; // [west, south, east, north]
  url: string;
}

function overlayType(filename: string): string {
  return filename.replace(/\.(?:png|jpg)$/, "").split("_").pop() || filename;
}

function maskImageToPolygon(
  imageUrl: string,
  bounds: [number, number, number, number],
  geometry: GeoJSON.Geometry,
): Promise<string> {
  const [west, south, east, north] = bounds;
  const rings =
    geometry.type === "Polygon"
      ? geometry.coordinates
      : geometry.type === "MultiPolygon"
        ? geometry.coordinates[0]
        : null;
  if (!rings) return Promise.resolve(imageUrl);

  return new Promise((resolve) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => {
      const canvas = document.createElement("canvas");
      canvas.width = img.width;
      canvas.height = img.height;
      const ctx = canvas.getContext("2d")!;

      ctx.beginPath();
      rings[0].forEach(([lng, lat]: number[], i: number) => {
        const x = ((lng - west) / (east - west)) * img.width;
        const y = ((north - lat) / (north - south)) * img.height;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.closePath();
      ctx.clip();
      ctx.drawImage(img, 0, 0);

      canvas.toBlob(
        (blob) => resolve(blob ? URL.createObjectURL(blob) : imageUrl),
        "image/png",
      );
    };
    img.onerror = () => resolve(imageUrl);
    img.src = imageUrl;
  });
}

interface AppState {
  conversations: Conversation[];
  activeConversationId: string | null;
  messages: ChatMessage[];
  aoi: AOI | null;
  isAgentRunning: boolean;
  streaming: StreamingMessage | null;
  sidebarOpen: boolean;
  overlayImagery: OverlayImage[];

  _wsStopFn: (() => void) | null;
  _wsDisconnectFn: (() => void) | null;

  setAoi: (aoi: AOI | null) => void;
  setSidebarOpen: (open: boolean) => void;
  addOverlayImagery: (filename: string) => Promise<void>;
  removeOverlayImagery: (filename: string) => void;

  loadConversations: () => Promise<void>;
  createConversation: () => Promise<string>;
  selectConversation: (id: string) => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;

  addUserMessage: (content: string) => void;
  setAgentRunning: (running: boolean) => void;
  handleWsEvent: (event: WsEvent) => void;
  finalizeAssistantMessage: (content: string, imagery_files: string[]) => void;

  registerWsCallbacks: (stop: () => void, disconnect: () => void) => void;
  clearWsCallbacks: () => void;
  stopAgent: () => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  conversations: [],
  activeConversationId: null,
  messages: [],
  aoi: null,
  isAgentRunning: false,
  streaming: null,
  sidebarOpen: false,
  overlayImagery: [],

  _wsStopFn: null,
  _wsDisconnectFn: null,

  setAoi: (aoi) => set({ aoi }),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  addOverlayImagery: async (filename) => {
    const existing = get().overlayImagery;
    if (existing.some((o) => o.filename === filename)) return;
    try {
      const data = await api.imageryBounds(filename);

      const aoi = get().aoi;
      let url = api.imageryUrl(filename);
      if (aoi?.geometry) {
        url = await maskImageToPolygon(url, data.bounds, aoi.geometry);
      }

      const newType = overlayType(filename);
      set((s) => {
        const kept = s.overlayImagery.filter((o) => {
          if (overlayType(o.filename) === newType) {
            if (o.url.startsWith("blob:")) URL.revokeObjectURL(o.url);
            return false;
          }
          return true;
        });
        return { overlayImagery: [...kept, { filename, bounds: data.bounds, url }] };
      });
    } catch (err) {
      console.warn(`Could not fetch bounds for ${filename}, skipping overlay`);
    }
  },
  removeOverlayImagery: (filename) =>
    set((s) => {
      const removed = s.overlayImagery.find((o) => o.filename === filename);
      if (removed?.url.startsWith("blob:")) URL.revokeObjectURL(removed.url);
      return { overlayImagery: s.overlayImagery.filter((o) => o.filename !== filename) };
    }),

  loadConversations: async () => {
    const convs = await api.listConversations();
    set({ conversations: convs });
  },

  createConversation: async () => {
    const conv = await api.createConversation();
    set((s) => ({
      conversations: [conv, ...s.conversations],
      activeConversationId: conv.id,
      messages: [],
      streaming: null,
      overlayImagery: [],
    }));
    return conv.id;
  },

  selectConversation: async (id) => {
    const state = get();
    if (state.isAgentRunning) {
      state._wsDisconnectFn?.();
      set({ isAgentRunning: false, streaming: null });
    }
    const detail = await api.getConversation(id);
    set({
      activeConversationId: id,
      messages: detail.messages,
      streaming: null,
      overlayImagery: [],
    });
  },

  deleteConversation: async (id) => {
    const state = get();
    if (state.activeConversationId === id && state.isAgentRunning) {
      state._wsDisconnectFn?.();
    }
    await api.deleteConversation(id);
    const remaining = state.conversations.filter((c) => c.id !== id);
    const isActive = state.activeConversationId === id;
    set({
      conversations: remaining,
      activeConversationId: isActive ? null : state.activeConversationId,
      messages: isActive ? [] : state.messages,
      streaming: isActive ? null : state.streaming,
      isAgentRunning: isActive ? false : state.isAgentRunning,
      overlayImagery: isActive ? [] : state.overlayImagery,
    });
  },

  addUserMessage: (content) =>
    set((s) => ({
      messages: [
        ...s.messages,
        {
          id: crypto.randomUUID(),
          role: "user",
          content,
          created_at: new Date().toISOString(),
        },
      ],
    })),

  setAgentRunning: (running) =>
    set({
      isAgentRunning: running,
      streaming: running ? { elements: [], imagery_files: [] } : null,
    }),

  handleWsEvent: (event) =>
    set((s) => {
      if (!s.streaming) return s;
      const elements = [...s.streaming.elements];
      let imagery_files = s.streaming.imagery_files;

      switch (event.type) {
        case "token": {
          const last = elements[elements.length - 1];
          if (last?.kind === "text") {
            elements[elements.length - 1] = { kind: "text", content: last.content + event.content };
          } else {
            elements.push({ kind: "text", content: event.content });
          }
          break;
        }
        case "tool_start":
          elements.push({ kind: "tool", event: { tool: event.tool || "unknown", status: "running" } });
          break;
        case "tool_end": {
          for (let i = elements.length - 1; i >= 0; i--) {
            const el = elements[i];
            if (el.kind === "tool" && el.event.tool === event.tool && el.event.status === "running") {
              elements[i] = {
                kind: "tool",
                event: { ...el.event, status: "done", output: event.content, imagery_files: event.imagery_files },
              };
              break;
            }
          }
          if (event.imagery_files) {
            imagery_files = [...imagery_files, ...event.imagery_files];
          }
          break;
        }
        case "error": {
          elements.push({ kind: "text", content: `\n\n**Error:** ${event.content}` });
          break;
        }
      }

      return { streaming: { elements, imagery_files } };
    }),

  finalizeAssistantMessage: (content, imagery_files) =>
    set((s) => ({
      messages: [
        ...s.messages,
        {
          id: crypto.randomUUID(),
          role: "assistant",
          content: content || "(Stopped by user)",
          metadata_json: imagery_files.length ? { imagery_files } : null,
          created_at: new Date().toISOString(),
        },
      ],
      streaming: null,
      isAgentRunning: false,
    })),

  registerWsCallbacks: (stop, disconnect) =>
    set({ _wsStopFn: stop, _wsDisconnectFn: disconnect }),

  clearWsCallbacks: () =>
    set({ _wsStopFn: null, _wsDisconnectFn: null }),

  stopAgent: () => {
    const state = get();
    if (state.isAgentRunning && state._wsStopFn) {
      state._wsStopFn();
    }
  },
}));
