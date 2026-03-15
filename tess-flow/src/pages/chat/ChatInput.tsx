import { useState, useRef, useEffect, useMemo } from "react";
import { ArrowRight, AtSign } from "lucide-react";
import { Agent } from "../../types";
import { AGENT_CATALOG } from "../../data/catalog";
import AgentIcon from "../../shared/AgentIcon";

interface ChatInputProps {
  agent?: Agent;
  onSend: (text: string, mentionedAgent?: Agent) => void;
  disabled?: boolean;
}

const ChatInput = ({ agent, onSend, disabled }: ChatInputProps) => {
  const [input, setInput] = useState("");
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [mentionIndex, setMentionIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const mentionRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const ta = textareaRef.current;
    if (ta) {
      ta.style.height = "auto";
      ta.style.height = Math.min(ta.scrollHeight, 150) + "px";
    }
  }, [input]);

  const mentionResults = useMemo(() => {
    if (mentionQuery === null) return [];
    const q = mentionQuery.toLowerCase();
    return AGENT_CATALOG.filter(
      (a) => a.name.toLowerCase().includes(q) || a.description.toLowerCase().includes(q)
    ).slice(0, 6);
  }, [mentionQuery]);

  const handleInputChange = (value: string) => {
    setInput(value);
    const cursor = textareaRef.current?.selectionStart ?? value.length;
    const before = value.slice(0, cursor);
    const match = before.match(/(^|[\s])@([^\s]*)$/);
    if (match) {
      setMentionQuery(match[2]);
      setMentionIndex(0);
    } else {
      setMentionQuery(null);
    }
  };

  const insertMention = (picked: Agent) => {
    const cursor = textareaRef.current?.selectionStart ?? input.length;
    const before = input.slice(0, cursor);
    const atIdx = before.lastIndexOf("@");
    const textBefore = input.slice(0, atIdx).trim();
    const textAfter = input.slice(cursor).trim();

    const cleanText = [textBefore, textAfter].filter(Boolean).join(" ");
    setMentionQuery(null);
    setInput("");
    onSend(cleanText || `Talk to ${picked.name}`, picked);
  };

  const handleSend = () => {
    const trimmed = input.trim();
    if (!trimmed || disabled) return;

    // Check if there's a standalone @mention in the text
    const mentionMatch = trimmed.match(/@(\w[\w\s]*?)(?:\s|$)/);
    if (mentionMatch) {
      const mentionName = mentionMatch[1].toLowerCase();
      const found = AGENT_CATALOG.find(
        (a) => a.name.toLowerCase() === mentionName || a.id.toLowerCase() === mentionName
      );
      if (found) {
        const cleanText = trimmed.replace(/@\w[\w\s]*?(?:\s|$)/, "").trim() || trimmed;
        onSend(cleanText, found);
        setInput("");
        return;
      }
    }

    onSend(trimmed);
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (mentionQuery !== null && mentionResults.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setMentionIndex((prev) => Math.min(prev + 1, mentionResults.length - 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setMentionIndex((prev) => Math.max(prev - 1, 0));
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        insertMention(mentionResults[mentionIndex]);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setMentionQuery(null);
        return;
      }
    }

    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const hasContent = input.trim().length > 0;

  return (
    <div className="chat-input-area">
      <div className={`chat-input-bar${hasContent ? " has-content" : ""}`}>
        {agent && (
          <span className="chat-input-agent-badge">
            <AgentIcon name={agent.iconName} size={11} />
            {agent.name}
          </span>
        )}
        <div className="chat-input-wrap">
          <textarea
            ref={textareaRef}
            className="chat-input"
            placeholder={agent ? `Message ${agent.name}…` : "Ask anything, or type @ to pick an agent…"}
            value={input}
            rows={1}
            onChange={(e) => handleInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={disabled}
          />
          {mentionQuery !== null && mentionResults.length > 0 && (
            <div className="mention-dropdown" ref={mentionRef}>
              <div className="mention-dropdown-header">
                <AtSign size={11} strokeWidth={2} />
                <span>Select an agent</span>
              </div>
              {mentionResults.map((a, i) => (
                <button
                  key={a.id}
                  type="button"
                  className={`mention-item ${i === mentionIndex ? "active" : ""}`}
                  onClick={() => insertMention(a)}
                  onMouseEnter={() => setMentionIndex(i)}
                >
                  <div className="mention-item-icon">
                    <AgentIcon name={a.iconName} size={14} />
                  </div>
                  <div className="mention-item-info">
                    <span className="mention-item-name">{a.name}</span>
                    <span className="mention-item-desc">{a.category}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>

        <button
          type="button"
          className="chat-send-btn"
          onClick={handleSend}
          aria-label="Send message"
        >
          <ArrowRight size={15} strokeWidth={2.3} />
        </button>
      </div>
    </div>
  );
};

export default ChatInput;
