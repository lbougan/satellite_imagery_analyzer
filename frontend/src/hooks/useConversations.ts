import { useEffect } from "react";
import { useAppStore } from "../stores/appStore";

export function useConversations() {
  const loadConversations = useAppStore((s) => s.loadConversations);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);
}
