import { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import { api } from "../lib/api";
import { useAppStore } from "../stores/appStore";
import type { ChatMessage } from "../types";

const IMG_RE = /([\w][\w\-.]*\.(?:png|jpg))/g;
const IMG_REPLACE_RE = /[(]?([\w][\w\-.]*\.(?:png|jpg))[).,;:]*/g;

function replaceImageryRefs(text: string): string {
  return text.replace(IMG_REPLACE_RE, (_, fname) => `\n\n![${fname}](${api.imageryUrl(fname)})\n\n`);
}

interface Props {
  message: ChatMessage;
}

export default function MessageBubble({ message }: Props) {
  const addOverlay = useAppStore((s) => s.addOverlayImagery);
  const isUser = message.role === "user";
  const imageryFiles = message.metadata_json?.imagery_files || [];

  const processedContent = useMemo(() => {
    if (isUser) return message.content;
    return replaceImageryRefs(message.content);
  }, [message.content, isUser]);

  const inlineImageFiles = useMemo(() => {
    if (isUser) return new Set<string>();
    return new Set((message.content.match(IMG_RE) || []) as string[]);
  }, [message.content, isUser]);

  const remainingFiles = imageryFiles.filter((f) => !inlineImageFiles.has(f));

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"} mb-4`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-blue-600 text-white rounded-br-md"
            : "bg-slate-800 text-slate-100 rounded-bl-md border border-slate-700"
        }`}
      >
        {!isUser && (
          <div className="text-[10px] text-slate-500 uppercase tracking-widest mb-1 font-medium">
            Agent
          </div>
        )}

        <div className="prose prose-invert prose-sm max-w-none [&>p]:mb-2 [&>p:last-child]:mb-0 break-words overflow-hidden">
          <ReactMarkdown
            remarkPlugins={[remarkGfm, remarkBreaks]}
            components={{
              img: ({ src, alt }) => {
                const filename = src ? src.split("/").pop() || "" : "";
                return (
                  <span className="block relative group my-3">
                    <img
                      src={src}
                      alt={alt || "Satellite imagery"}
                      crossOrigin="anonymous"
                      className="rounded-lg max-h-64 w-full object-cover border border-slate-600"
                      loading="lazy"
                    />
                    {(filename.endsWith(".png") || filename.endsWith(".jpg")) && (
                      <button
                        onClick={() => addOverlay(filename)}
                        className="absolute bottom-2 right-2 bg-slate-900/80 hover:bg-blue-600
                                   text-xs text-white px-2 py-1 rounded-md opacity-0
                                   group-hover:opacity-100 transition-opacity backdrop-blur-sm"
                      >
                        Show on map
                      </button>
                    )}
                  </span>
                );
              },
            }}
          >
            {processedContent}
          </ReactMarkdown>
        </div>

        {remainingFiles.length > 0 && (
          <div className="mt-3 space-y-2">
            {remainingFiles.map((file) => (
              <div key={file} className="relative group">
                <img
                  src={api.imageryUrl(file)}
                  alt={file}
                  crossOrigin="anonymous"
                  className="rounded-lg max-h-64 w-full object-cover border border-slate-600"
                  loading="lazy"
                />
                <button
                  onClick={() => addOverlay(file)}
                  className="absolute bottom-2 right-2 bg-slate-900/80 hover:bg-blue-600
                             text-xs text-white px-2 py-1 rounded-md opacity-0
                             group-hover:opacity-100 transition-opacity backdrop-blur-sm"
                >
                  Show on map
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
