import type { ToolEvent } from "../stores/appStore";

interface Props {
  events: ToolEvent[];
}

const TOOL_LABELS: Record<string, string> = {
  search_imagery: "Searching for satellite imagery",
  download_imagery: "Downloading spectral bands",
  download_imagery_batch: "Downloading spectral bands",
  compute_index: "Computing spectral index",
  analyze_image: "Analyzing image with AI vision",
  compare_images: "Comparing scenes for changes",
};

export default function ToolStatusCard({ events }: Props) {
  if (events.length === 0) return null;

  return (
    <div className="space-y-2">
      {events.map((ev, i) => (
        <div
          key={`${ev.tool}-${i}`}
          className="bg-slate-800/50 border border-slate-700 rounded-xl px-4 py-3"
        >
          <div className="flex items-center gap-2">
            {ev.status === "running" ? (
              <div className="w-2 h-2 bg-amber-400 rounded-full animate-pulse" />
            ) : (
              <div className="w-2 h-2 bg-emerald-400 rounded-full" />
            )}
            <span className="text-xs font-medium text-slate-300">
              {TOOL_LABELS[ev.tool] || ev.tool}
            </span>
            {ev.status === "running" && (
              <span className="text-[10px] text-slate-500 ml-auto">running...</span>
            )}
          </div>

          {ev.status === "done" && ev.output && (
            <details className="mt-2">
              <summary className="text-[11px] text-slate-500 cursor-pointer hover:text-slate-400">
                View output
              </summary>
              <pre className="mt-1 text-[11px] text-slate-400 whitespace-pre-wrap break-all leading-relaxed
                              max-h-32 overflow-y-auto overflow-x-hidden">
                {ev.output}
              </pre>
            </details>
          )}
        </div>
      ))}
    </div>
  );
}
