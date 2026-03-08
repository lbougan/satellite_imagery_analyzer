import { useRef, useCallback } from "react";
import { useAppStore } from "../stores/appStore";
import type { WsEvent } from "../types";

const WS_BASE = import.meta.env.VITE_WS_BASE_URL || "ws://localhost:8000";

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const store = useAppStore();

  const sendMessage = useCallback(
    (conversationId: string, content: string, aoiGeoJson?: any) => {
      if (wsRef.current) {
        wsRef.current.close();
      }

      const ws = new WebSocket(`${WS_BASE}/ws/chat/${conversationId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        store.addUserMessage(content);
        store.setAgentRunning(true);
        store.registerWsCallbacks(
          () => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send(JSON.stringify({ action: "stop" }));
            }
          },
          () => {
            ws.close();
            wsRef.current = null;
          }
        );
        ws.send(JSON.stringify({ content, aoi_geojson: aoiGeoJson || null }));
      };

      ws.onmessage = (event) => {
        const data: WsEvent = JSON.parse(event.data);

        if (data.type === "done" || data.type === "stopped") {
          store.finalizeAssistantMessage(data.content, data.imagery_files || []);
        } else {
          store.handleWsEvent(data);
        }
      };

      ws.onerror = () => {
        store.setAgentRunning(false);
      };

      ws.onclose = () => {
        wsRef.current = null;
        store.clearWsCallbacks();
      };
    },
    [store]
  );

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  return { sendMessage, disconnect };
}
