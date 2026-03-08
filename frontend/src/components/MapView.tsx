import { useRef, useCallback } from "react";
import Map, { NavigationControl, Source, Layer, useControl } from "react-map-gl";
import type { MapRef } from "react-map-gl";
import MapboxDraw from "@mapbox/mapbox-gl-draw";
import { useAppStore } from "../stores/appStore";
import type { AOI } from "../types";

import "mapbox-gl/dist/mapbox-gl.css";

const MAPBOX_TOKEN = import.meta.env.VITE_MAPBOX_TOKEN || "";

function DrawControl({ onUpdate, onDelete, drawRef }: {
  onUpdate: (features: GeoJSON.Feature[]) => void;
  onDelete: () => void;
  drawRef: React.MutableRefObject<MapboxDraw | null>;
}) {
  const draw = useControl<MapboxDraw>(
    () => new MapboxDraw({
      displayControlsDefault: false,
      controls: { polygon: true, rectangle: true, trash: true },
    }),
    ({ map }) => {
      map.on("draw.create", handleUpdate);
      map.on("draw.update", handleUpdate);
      map.on("draw.delete", onDelete);
    },
    ({ map }) => {
      map.off("draw.create", handleUpdate);
      map.off("draw.update", handleUpdate);
      map.off("draw.delete", onDelete);
    },
    { position: "top-left" }
  );

  drawRef.current = draw;

  function handleUpdate(e: any) {
    onUpdate(e.features);
  }

  return null;
}

export default function MapView() {
  const mapRef = useRef<MapRef | null>(null);
  const drawRef = useRef<MapboxDraw | null>(null);
  const setAoi = useAppStore((s) => s.setAoi);
  const overlayImagery = useAppStore((s) => s.overlayImagery);
  const removeOverlay = useAppStore((s) => s.removeOverlayImagery);
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const setSidebarOpen = useAppStore((s) => s.setSidebarOpen);
  const aoi = useAppStore((s) => s.aoi);

  const handleDrawUpdate = useCallback((features: GeoJSON.Feature[]) => {
    if (features.length > 0) {
      setAoi(features[features.length - 1] as AOI);
    }
  }, [setAoi]);

  const handleDrawDelete = useCallback(() => {
    setAoi(null);
  }, [setAoi]);

  const handleClearAoi = useCallback(() => {
    drawRef.current?.deleteAll();
    setAoi(null);
  }, [setAoi]);

  return (
    <div className="w-full h-full relative">
      <Map
        ref={mapRef}
        initialViewState={{
          longitude: 0,
          latitude: 20,
          zoom: 2.5,
        }}
        mapStyle="mapbox://styles/mapbox/satellite-streets-v12"
        mapboxAccessToken={MAPBOX_TOKEN}
        style={{ width: "100%", height: "100%" }}
      >
        <NavigationControl position="bottom-right" />
        <DrawControl onUpdate={handleDrawUpdate} onDelete={handleDrawDelete} drawRef={drawRef} />

        {overlayImagery.map(({ filename, bounds, url }) => {
          const [west, south, east, north] = bounds;
          return (
            <Source
              key={filename}
              id={`overlay-${filename}`}
              type="image"
              url={url}
              coordinates={[
                [west, north],
                [east, north],
                [east, south],
                [west, south],
              ]}
            >
              <Layer
                id={`layer-${filename}`}
                type="raster"
                paint={{ "raster-opacity": 0.85 }}
              />
            </Source>
          );
        })}
      </Map>

      {!sidebarOpen && (
        <button
          onClick={() => setSidebarOpen(true)}
          className="absolute top-28 left-2.5 z-10 bg-slate-900/90 hover:bg-slate-800
                     backdrop-blur-sm text-slate-300 hover:text-white px-2 py-2
                     rounded-lg text-sm transition-colors border border-slate-700"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M3 12h18M3 6h18M3 18h18" />
          </svg>
        </button>
      )}

      {aoi && (
        <div className="absolute bottom-4 left-4 z-10 bg-slate-900/90 backdrop-blur-sm
                        text-xs text-slate-400 px-3 py-2 rounded-lg border border-slate-700
                        flex items-center gap-2">
          AOI selected
          <button
            onClick={handleClearAoi}
            className="text-slate-500 hover:text-red-400 transition-colors p-0.5"
            title="Clear AOI"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
      )}

      {overlayImagery.length > 0 && (
        <div className="absolute top-4 right-4 z-10 bg-slate-900/90 backdrop-blur-sm
                        rounded-lg border border-slate-700 p-3 max-w-xs">
          <div className="text-[10px] text-slate-400 uppercase tracking-widest mb-2 font-medium">
            Overlays
          </div>
          <div className="space-y-1.5">
            {overlayImagery.map(({ filename }) => {
              const label = filename
                .replace(/\.png$/, "")
                .split("_")
                .pop() || filename;
              return (
                <div
                  key={filename}
                  className="flex items-center justify-between gap-2 text-xs text-slate-300"
                >
                  <span className="truncate" title={filename}>
                    {label.toUpperCase()}
                  </span>
                  <button
                    onClick={() => removeOverlay(filename)}
                    className="shrink-0 text-slate-500 hover:text-red-400 transition-colors p-0.5"
                    title="Remove overlay"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M18 6L6 18M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}
