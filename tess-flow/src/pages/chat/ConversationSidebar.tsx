import { Search, X, MessageSquarePlus, PanelLeftClose } from "lucide-react";
import { useState, useRef, useEffect } from "react";
import { Conversation } from "../../types";

interface ConversationSidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  isOpen: boolean;
  onToggle: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onDelete: (id: string) => void;
}

const getRelativeTime = (isoDate: string) => {
  const days = Math.floor((Date.now() - new Date(isoDate).getTime()) / 86400000);
  if (days === 0) return "Today";
  if (days === 1) return "Yesterday";
  if (days <= 7) return "Previous 7 Days";
  return "Older";
};

const ConversationSidebar = ({ conversations, activeId, isOpen, onToggle, onSelect, onNew, onDelete }: ConversationSidebarProps) => {
  const [searchQuery, setSearchQuery] = useState("");
  const searchInputRef = useRef<HTMLInputElement>(null);
  const filtered = conversations.filter((c) => !searchQuery || c.title.toLowerCase().includes(searchQuery.toLowerCase()));
  const sorted = [...filtered].sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime());

  const groups: Record<string, Conversation[]> = {};
  for (const c of sorted) {
    const groupName = getRelativeTime(c.updatedAt);
    (groups[groupName] ??= []).push(c);
  }

  // Focus search input when sidebar opens
  useEffect(() => {
    if (isOpen && searchInputRef.current) {
      const timer = setTimeout(() => searchInputRef.current?.focus(), 300);
      return () => clearTimeout(timer);
    }
  }, [isOpen]);

  return (
    <aside className={`conv-sidebar ${isOpen ? "open" : "closed"}`}>
      <div className="conv-sidebar-inner">
        {/* Header */}
        <div className="conv-sidebar-header">
          <div className="conv-sidebar-title-row">
            <h2 className="conv-sidebar-title">Chats</h2>
            {conversations.length > 0 && (
              <span className="conv-sidebar-count">{conversations.length}</span>
            )}
          </div>
          <div className="conv-sidebar-actions">
            <button type="button" className="conv-icon-btn conv-new-btn" onClick={onNew} aria-label="New chat" title="New chat">
              <MessageSquarePlus size={16} strokeWidth={1.8} />
            </button>
            <button type="button" className="conv-icon-btn" onClick={onToggle} aria-label="Close sidebar" title="Close sidebar">
              <PanelLeftClose size={18} strokeWidth={1.7} />
            </button>
          </div>
        </div>
        
        {/* Search */}
        <div className="conv-search-wrap">
          <Search size={14} className="conv-search-icon" />
          <input 
            ref={searchInputRef}
            type="text" 
            className="conv-search" 
            placeholder="Search chats…" 
            value={searchQuery} 
            onChange={(e) => setSearchQuery(e.target.value)}
            tabIndex={isOpen ? 0 : -1}
          />
          {searchQuery && (
            <button type="button" onClick={() => setSearchQuery("")} className="conv-search-clear">
              <X size={12} strokeWidth={2.5} />
            </button>
          )}
        </div>

        {/* Conversation list */}
        <div className="conv-list">
          {sorted.length === 0 && (
            <div className="conv-empty">
              <div className="conv-empty-icon">
                <MessageSquarePlus size={24} strokeWidth={1.5} />
              </div>
              <p>{searchQuery ? "No matches found" : "No conversations yet"}</p>
              {!searchQuery && (
                <span className="conv-empty-hint">Start a new chat to begin</span>
              )}
            </div>
          )}
          
          {["Today", "Yesterday", "Previous 7 Days", "Older"].map((groupName) => {
            const items = groups[groupName];
            if (!items || items.length === 0) return null;
            
            return (
              <div key={groupName} className="conv-group">
                <p className="conv-group-label">{groupName}</p>
                {items.map((c) => (
                  <button 
                    key={c.id} 
                    type="button" 
                    className={`conv-item ${c.id === activeId ? "active" : ""}`} 
                    onClick={() => onSelect(c.id)}
                    tabIndex={isOpen ? 0 : -1}
                  >
                    <div className="conv-item-content">
                      <span className="conv-item-title">{c.title}</span>
                    </div>
                    <button 
                      type="button" 
                      className="conv-item-delete" 
                      onClick={(e) => { e.stopPropagation(); onDelete(c.id); }}
                      aria-label="Delete chat"
                      title="Delete chat"
                      tabIndex={isOpen ? 0 : -1}
                    >
                      <X size={13} strokeWidth={2} />
                    </button>
                  </button>
                ))}
              </div>
            );
          })}
        </div>
      </div>
    </aside>
  );
};

export default ConversationSidebar;
