import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import { api } from "../lib/api";
import ToolStatusCard from "./ToolStatusCard";
import type { StreamElement, ToolEvent } from "../stores/appStore";

const IMG_REPLACE_RE = /[(]?([\w][\w\-.]*\.(?:png|jpg))[).,;:]*/g;

function replaceImageryRefs(text: string): string {
  return text.replace(IMG_REPLACE_RE, (_, fname) => `\n\n![${fname}](${api.imageryUrl(fname)})\n\n`);
}

interface Props {
  elements: StreamElement[];
}

function groupElements(elements: StreamElement[]) {
  const groups: Array<{ kind: "text"; content: string } | { kind: "tools"; events: ToolEvent[] }> = [];
  for (const el of elements) {
    if (el.kind === "text") {
      groups.push({ kind: "text", content: el.content });
    } else {
      const last = groups[groups.length - 1];
      if (last?.kind === "tools") {
        last.events.push(el.event);
      } else {
        groups.push({ kind: "tools", events: [el.event] });
      }
    }
  }
  return groups;
}

export default function StreamingMessage({ elements }: Props) {
  const groups = useMemo(() => groupElements(elements), [elements]);

  const isAllToolsRunning =
    elements.length > 0 &&
    elements.every((e) => e.kind === "tool" && e.event.status === "running");

  const lastGroup = groups[groups.length - 1];
  const isStreaming = lastGroup?.kind === "text";

  return (
    <div className="flex justify-start mb-4">
      <div className="max-w-[85%] space-y-3">
        {groups.map((group, i) => {
          if (group.kind === "tools") {
            return <ToolStatusCard key={`tools-${i}`} events={group.events} />;
          }

          const processed = replaceImageryRefs(group.content);
          const showCursor = isStreaming && i === groups.length - 1;

          return (
            <div
              key={`text-${i}`}
              className="bg-slate-800 text-slate-100 rounded-2xl rounded-bl-md
                         border border-slate-700 px-4 py-3"
            >
              {i === 0 && (
                <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-1 font-medium">
                  Agent
                </div>
              )}
              <div className="prose prose-invert prose-sm max-w-none [&>p]:mb-2 [&>p:last-child]:mb-0 break-words overflow-hidden">
                <ReactMarkdown
                  remarkPlugins={[remarkGfm, remarkBreaks]}
                  components={{
                    img: ({ src, alt }) => (
                      <span className="block my-3">
                        <img
                          src={src}
                          alt={alt || "Satellite imagery"}
                          crossOrigin="anonymous"
                          className="rounded-lg max-h-64 w-full object-cover border border-slate-600"
                          loading="lazy"
                        />
                      </span>
                    ),
                  }}
                >
                  {processed}
                </ReactMarkdown>
              </div>
              {showCursor && (
                <span className="inline-block w-1.5 h-4 bg-blue-400 animate-pulse ml-0.5 align-text-bottom rounded-sm" />
              )}
            </div>
          );
        })}

        {elements.length === 0 && (
          <div className="text-xs text-slate-500 mt-2 flex items-center gap-2">
            <div className="flex gap-1">
              <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
            Agent is working...
          </div>
        )}

        {isAllToolsRunning && groups.length === 1 && (
          <div className="text-xs text-slate-500 mt-2 flex items-center gap-2">
            <div className="flex gap-1">
              <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
              <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
              <div className="w-1.5 h-1.5 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
            </div>
            Agent is working...
          </div>
        )}
      </div>
    </div>
  );
}
