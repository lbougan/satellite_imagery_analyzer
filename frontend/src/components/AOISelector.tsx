import { useAppStore } from "../stores/appStore";

export default function AOISelector() {
  const aoi = useAppStore((s) => s.aoi);
  const setAoi = useAppStore((s) => s.setAoi);

  if (!aoi) return null;

  const geom = aoi.geometry;
  const coords =
    geom.type === "Polygon"
      ? (geom as GeoJSON.Polygon).coordinates[0]
      : [];

  const bbox = coords.length
    ? [
        Math.min(...coords.map((c) => c[0])),
        Math.min(...coords.map((c) => c[1])),
        Math.max(...coords.map((c) => c[0])),
        Math.max(...coords.map((c) => c[1])),
      ]
    : null;

  return (
    <div className="bg-slate-800/50 border border-slate-700 rounded-xl px-3 py-2 text-xs">
      <div className="flex items-center justify-between">
        <span className="text-slate-400 font-medium">Area of Interest</span>
        <button
          onClick={() => setAoi(null)}
          className="text-slate-500 hover:text-red-400 text-sm"
        >
          &times;
        </button>
      </div>
      {bbox && (
        <div className="text-[10px] text-slate-500 mt-1 font-mono">
          {bbox.map((v) => v.toFixed(4)).join(", ")}
        </div>
      )}
    </div>
  );
}
