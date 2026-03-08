import { useConversations } from "./hooks/useConversations";
import { useAppStore } from "./stores/appStore";
import Sidebar from "./components/Sidebar";
import MapView from "./components/MapView";
import ChatPanel from "./components/ChatPanel";

export default function App() {
  useConversations();
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);

  return (
    <div className="h-screen w-screen flex overflow-hidden bg-slate-950">
      {sidebarOpen && <Sidebar />}

      <div className="flex-1 flex min-w-0">
        <div className="w-[60%] h-full relative">
          <MapView />
        </div>

        <div className="w-[40%] h-full border-l border-slate-800">
          <ChatPanel />
        </div>
      </div>
    </div>
  );
}
