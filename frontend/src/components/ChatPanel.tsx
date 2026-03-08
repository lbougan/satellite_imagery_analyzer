import { useState, useRef, useEffect } from "react";
import { useAppStore } from "../stores/appStore";
import { useWebSocket } from "../hooks/useWebSocket";
import MessageBubble from "./MessageBubble";
import StreamingMessage from "./StreamingMessage";

export default function ChatPanel() {
  const [input, setInput] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { sendMessage } = useWebSocket();

  const messages = useAppStore((s) => s.messages);
  const streaming = useAppStore((s) => s.streaming);
  const isAgentRunning = useAppStore((s) => s.isAgentRunning);
  const activeConversationId = useAppStore((s) => s.activeConversationId);
  const createConversation = useAppStore((s) => s.createConversation);
  const stopAgent = useAppStore((s) => s.stopAgent);
  const aoi = useAppStore((s) => s.aoi);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streaming?.elements]);

  const handleSend = async () => {
    const trimmed = input.trim();
    if (!trimmed || isAgentRunning) return;

    let convId = activeConversationId;
    if (!convId) {
      convId = await createConversation();
    }

    setInput("");
    const aoiGeoJson = aoi ? aoi.geometry : undefined;
    sendMessage(convId, trimmed, aoiGeoJson);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="h-full flex flex-col bg-slate-950">
      <div className="px-4 py-3 border-b border-slate-800 flex items-center gap-3">
        <div className="w-2 h-2 bg-emerald-400 rounded-full" />
        <h1 className="text-sm font-semibold text-slate-200 tracking-wide">
          Satellite Imagery Agent
        </h1>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {messages.length === 0 && !streaming && (
          <div className="h-full flex flex-col items-center justify-center text-center px-8">
            <div className="text-4xl mb-4">🛰️</div>
            <h2 className="text-lg font-semibold text-slate-300 mb-2">
              Satellite Imagery Agent
            </h2>
            <p className="text-sm text-slate-500 max-w-sm leading-relaxed">
              Draw an area of interest on the map, then ask me about satellite imagery,
              vegetation health, water bodies, land use changes, and more.
            </p>
            <div className="mt-6 space-y-2 text-left">
              {[
                "Show me vegetation health for this area in the last month",
                "Find the most recent cloud-free image of this region",
                "Compare land cover between January and June 2025",
              ].map((suggestion) => (
                <button
                  key={suggestion}
                  onClick={() => setInput(suggestion)}
                  className="block w-full text-left text-xs text-slate-400 hover:text-blue-400
                             bg-slate-900 hover:bg-slate-800 px-4 py-2.5 rounded-lg
                             border border-slate-800 hover:border-slate-700 transition-colors"
                >
                  {suggestion}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}

        {streaming && (
          <StreamingMessage elements={streaming.elements} />
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className="px-4 py-3 border-t border-slate-800">
        {aoi && (
          <div className="mb-2 flex items-center gap-1.5 text-[11px] text-emerald-400">
            <div className="w-1.5 h-1.5 bg-emerald-400 rounded-full" />
            AOI will be included with your message
          </div>
        )}
        <div className="flex items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              isAgentRunning ? "Agent is working..." : "Ask about satellite imagery..."
            }
            disabled={isAgentRunning}
            rows={1}
            className="flex-1 bg-slate-900 text-slate-100 placeholder-slate-600
                       rounded-xl px-4 py-3 text-sm resize-none border border-slate-800
                       focus:border-blue-500 focus:outline-none transition-colors
                       disabled:opacity-50"
          />
          {isAgentRunning ? (
            <button
              onClick={stopAgent}
              className="bg-red-600 hover:bg-red-500 text-white px-4 py-3 rounded-xl
                         text-sm font-medium transition-colors flex items-center gap-1.5"
            >
              <svg className="w-4 h-4" viewBox="0 0 16 16" fill="currentColor">
                <rect x="3" y="3" width="10" height="10" rx="1" />
              </svg>
              Stop
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!input.trim()}
              className="bg-blue-600 hover:bg-blue-500 disabled:bg-slate-800
                         disabled:text-slate-600 text-white px-4 py-3 rounded-xl
                         text-sm font-medium transition-colors"
            >
              Send
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
