const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API ${res.status}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  listConversations: () => request<any[]>("/api/conversations"),

  createConversation: (title?: string) =>
    request<any>("/api/conversations", {
      method: "POST",
      body: JSON.stringify({ title: title || "New Conversation" }),
    }),

  getConversation: (id: string) => request<any>(`/api/conversations/${id}`),

  deleteConversation: (id: string) =>
    request<void>(`/api/conversations/${id}`, { method: "DELETE" }),

  imageryUrl: (filename: string) => `${API_BASE}/api/imagery/${filename}`,

  imageryBounds: (filename: string) =>
    request<{ bounds: [number, number, number, number] }>(`/api/imagery/bounds/${filename}`),
};
