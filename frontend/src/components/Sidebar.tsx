import { useAppStore } from "../stores/appStore";

export default function Sidebar() {
  const conversations = useAppStore((s) => s.conversations);
  const activeId = useAppStore((s) => s.activeConversationId);
  const selectConversation = useAppStore((s) => s.selectConversation);
  const deleteConversation = useAppStore((s) => s.deleteConversation);
  const createConversation = useAppStore((s) => s.createConversation);
  const setSidebarOpen = useAppStore((s) => s.setSidebarOpen);

  return (
    <div className="w-72 h-full bg-slate-900 border-r border-slate-800 flex flex-col">
      <div className="p-4 border-b border-slate-800 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
          Conversations
        </h2>
        <button
          onClick={() => setSidebarOpen(false)}
          className="text-slate-500 hover:text-slate-300 text-lg"
        >
          &times;
        </button>
      </div>

      <button
        onClick={createConversation}
        className="mx-3 mt-3 px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-sm
                   rounded-lg transition-colors flex items-center gap-2"
      >
        <span className="text-lg leading-none">+</span>
        New Conversation
      </button>

      <div className="flex-1 overflow-y-auto mt-2 px-2 space-y-1">
        {conversations.map((conv) => (
          <div
            key={conv.id}
            onClick={() => selectConversation(conv.id)}
            className={`group flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer
                        transition-colors text-sm ${
                          conv.id === activeId
                            ? "bg-slate-800 text-white"
                            : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-200"
                        }`}
          >
            <span className="truncate flex-1">{conv.title}</span>
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (window.confirm("Delete this conversation?")) {
                  deleteConversation(conv.id);
                }
              }}
              className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-red-400
                         ml-2 transition-opacity"
              title="Delete conversation"
            >
              &times;
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
