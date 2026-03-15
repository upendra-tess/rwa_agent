/**
 * ConversationHistorySidebar — Left sidebar showing workflow conversation history.
 * Similar to ChatGPT's conversation list.
 */
import { Plus, MessageSquare, Trash2 } from "lucide-react";

export interface WorkflowConversation {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  hasWorkflow: boolean;
}

interface ConversationHistorySidebarProps {
  conversations: WorkflowConversation[];
  activeId: string | null;
  isOpen: boolean;
  onToggle: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}

const ConversationHistorySidebar = ({
  conversations,
  activeId,
  isOpen,
  // onToggle — intentionally unused (panel is controlled externally)
  onSelect,
  onNew,
  onDelete,
}: ConversationHistorySidebarProps) => {
  return (
    <div className={`studio-history-sidebar ${isOpen ? "open" : "closed"}`}>
      <div className="studio-history-sidebar-inner">
        {/* Header */}
        <div className="studio-history-header">
          <button type="button" className="studio-history-new-btn" onClick={onNew}>
            <Plus size={16} strokeWidth={2} />
            <span>New Workflow</span>
          </button>
        </div>

        {/* Conversation list */}
        <div className="studio-history-list">
          {conversations.length === 0 ? (
            <div className="studio-history-empty">
              <MessageSquare size={24} strokeWidth={1.5} style={{ opacity: 0.3 }} />
              <p>No conversations yet</p>
            </div>
          ) : (
            conversations.map((conv) => (
              <button
                key={conv.id}
                type="button"
                className={`studio-history-item ${conv.id === activeId ? "active" : ""}`}
                onClick={() => onSelect(conv.id)}
              >
                <MessageSquare size={14} strokeWidth={2} />
                <span className="studio-history-item-title">{conv.title}</span>
                <button
                  type="button"
                  className="studio-history-item-delete"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete(conv.id);
                  }}
                  aria-label="Delete conversation"
                >
                  <Trash2 size={12} strokeWidth={2} />
                </button>
              </button>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default ConversationHistorySidebar;
