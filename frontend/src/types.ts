export interface Conversation {
  id: string;
  title: string;
  created_at: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "tool";
  content: string;
  metadata_json?: {
    imagery_files?: string[];
    aoi_geojson?: GeoJSON.GeoJSON;
  } | null;
  created_at: string;
}

export interface ConversationDetail extends Conversation {
  messages: ChatMessage[];
}

export interface WsEvent {
  type: "token" | "tool_start" | "tool_end" | "done" | "stopped" | "error" | "status";
  content: string;
  tool?: string;
  imagery_files?: string[];
}

export interface AOI {
  type: "Feature";
  geometry: GeoJSON.Geometry;
  properties: Record<string, unknown>;
}
