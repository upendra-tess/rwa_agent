import { useState, useRef, useEffect, useCallback } from "react";
import { PanelLeft, ArrowDown, Sparkles, ArrowRight } from "lucide-react";
import { Agent, Conversation, ConversationMessage, AgentRun } from "../../types";
import { AGENT_CATALOG } from "../../data/catalog";
import { startRun } from "../../services/agentRunner";
import ConversationSidebar from "./ConversationSidebar";
import MessageBubble from "./MessageBubble";
import ChatInput from "./ChatInput";
import AgentSelector from "./AgentSelector";

const KEYWORDS: Record<string, string[]> = {
  "research-analyst":  ["research", "report", "summarise", "summarize", "analyse", "analyze", "compare", "trend", "defi", "web3"],
  "code-reviewer":     ["code", "review", "bug", "security", "solidity", "typescript", "python", "function", "lint"],
  "payment-ops":       ["payment", "invoice", "reconcile", "payout", "transaction", "usdc", "billing"],
  "data-analyst":      ["data", "csv", "analytics", "chart", "insight", "anomaly", "statistics", "dataset"],
  "security-auditor":  ["audit", "vulnerability", "smart contract", "cve", "exploit", "reentrancy"],
  "portfolio-tracker": ["portfolio", "wallet", "balance", "pnl", "rebalance", "holdings", "crypto", "btc", "eth"],
  "email-composer":    ["email", "draft", "compose", "follow-up", "outreach", "mail"],
  "scheduler":         ["schedule", "meeting", "calendar", "slot", "availability", "invite", "reschedule"],
  "seo-optimizer":     ["seo", "search engine", "keyword", "meta", "ranking", "backlink"],
  "social-writer":     ["social", "twitter", "linkedin", "instagram", "post", "hashtag", "thread"],
};

function discoverAgent(text: string): Agent | null {
  const lower = text.toLowerCase();
  let bestId: string | null = null;
  let bestScore = 0;
  for (const [id, kws] of Object.entries(KEYWORDS)) {
    const score = kws.filter((k) => lower.includes(k)).length;
    if (score > bestScore) { bestScore = score; bestId = id; }
  }
  if (bestId && bestScore > 0) return AGENT_CATALOG.find((a) => a.id === bestId) ?? null;
  return AGENT_CATALOG.find((a) => a.publisher === "Tesseris") ?? AGENT_CATALOG[0] ?? null;
}

interface ChatPageProps {
  installedAgents: Agent[];
  onInstallAgent: (agent: Agent) => void;
}

const ChatPage = ({ installedAgents, onInstallAgent }: ChatPageProps) => {
  const [convos, setConvos] = useState<Conversation[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [showPicker, setShowPicker] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const btmRef = useRef<HTMLDivElement>(null);
  const messagesRef = useRef<HTMLDivElement>(null);

  const active = convos.find((c) => c.id === activeId) ?? null;
  const agent = active ? AGENT_CATALOG.find((a) => a.id === active.agentId) : undefined;

  useEffect(() => {
    const el = messagesRef.current;
    if (el) {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    }
  }, [active?.messages.length, isThinking]);

  useEffect(() => {
    const el = messagesRef.current;
    if (!el) return;
    const handleScroll = () => {
      setShowScrollBtn(el.scrollHeight - el.scrollTop - el.clientHeight > 120);
    };
    el.addEventListener("scroll", handleScroll, { passive: true });
    return () => el.removeEventListener("scroll", handleScroll);
  }, [active?.id]);

  const ensureInstalled = useCallback((a: Agent) => {
    if (!installedAgents.some((x) => x.id === a.id)) onInstallAgent(a);
  }, [installedAgents, onInstallAgent]);

  const mkConvo = useCallback((title?: string): string => {
    const id = `c-${Date.now()}`;
    setConvos((p) => [{ id, title: title ?? "New Chat", agentId: "", messages: [], createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }, ...p]);
    setActiveId(id);
    setShowPicker(false);
    return id;
  }, []);

  const addMsg = useCallback((cid: string, m: ConversationMessage) => {
    setConvos((p) => p.map((c) => c.id === cid ? { ...c, messages: [...c.messages, m], updatedAt: new Date().toISOString() } : c));
  }, []);

  const updRun = useCallback((cid: string, mid: string, run: AgentRun) => {
    setConvos((p) => p.map((c) => c.id === cid ? {
      ...c,
      messages: c.messages.map((m) => m.id === mid ? { ...m, run: { ...run }, type: (run.status === "success" || run.status === "error" ? "run-complete" : "run-card") as ConversationMessage["type"] } : m),
      updatedAt: new Date().toISOString(),
    } : c));
  }, []);

  const execRun = useCallback((cid: string, ag: Agent, text: string) => {
    const inputs: Record<string, string> = {};
    if (ag.inputSchema.length > 0) {
      inputs[ag.inputSchema[0].key] = text;
      ag.inputSchema.slice(1).forEach((f) => { inputs[f.key] = f.defaultValue ?? ""; });
    }
    const rmid = `mr-${Date.now()}`;
    setIsThinking(false);
    const run = startRun(ag.id, inputs,
      (r) => updRun(cid, rmid, r),
      (r) => {
        updRun(cid, rmid, r);
        addMsg(cid, { id: `m-${Date.now()}`, role: "agent", text: r.output || "Task completed successfully.", timestamp: new Date().toISOString(), type: "text" });
      }
    );
    addMsg(cid, { id: rmid, role: "agent", text: "", timestamp: new Date().toISOString(), type: "run-card", runId: run.id, run: { ...run } });
  }, [addMsg, updRun]);

  const handleSend = useCallback((text: string, mentioned?: Agent) => {
    const userMsg: ConversationMessage = { id: `m-${Date.now()}`, role: "user", text, timestamp: new Date().toISOString(), type: "text" };
    if (active) {
      if (active.messages.length === 0) setConvos((p) => p.map((c) => c.id === active.id ? { ...c, title: text.slice(0, 50) } : c));
      addMsg(active.id, userMsg);
      setIsThinking(true);
      const target = mentioned ?? discoverAgent(text);
      if (!target) return;
      ensureInstalled(target);
      setTimeout(() => execRun(active.id, target, text), 600);
      return;
    }
    const target = mentioned ?? discoverAgent(text);
    if (!target) return;
    ensureInstalled(target);
    const cid = mkConvo(text.length > 50 ? text.slice(0, 50) + "…" : text);
    setTimeout(() => {
      addMsg(cid, userMsg);
      setIsThinking(true);
      setTimeout(() => execRun(cid, target, text), 600);
    }, 50);
  }, [active, addMsg, execRun, mkConvo, ensureInstalled]);

  return (
    <div className="chat-layout">
      <ConversationSidebar
        conversations={convos}
        activeId={activeId}
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
        onSelect={setActiveId}
        onNew={() => setActiveId(null)}
        onDelete={(id) => {
          setConvos((p) => p.filter((c) => c.id !== id));
          if (activeId === id) setActiveId(null);
        }}
      />

      <div className="chat-page">
        <button
          type="button"
          className={`chat-sidebar-toggle${!isSidebarOpen ? " visible" : ""}`}
          onClick={() => setIsSidebarOpen(true)}
          aria-label="Open sidebar"
          title="Open sidebar"
          tabIndex={isSidebarOpen ? -1 : 0}
        >
          <PanelLeft size={18} strokeWidth={1.7} />
        </button>
        <div className="chat-main">
          <div className="chat-messages" ref={messagesRef}>
            {!active ? (
              <div className="welcome-content">
                <div className="welcome-logo-wrap">
                  <img src="/tesseris-logo.png" alt="TessFlow" className="welcome-logo" />
                </div>
                <h1 className="welcome-title">What can I help you with?</h1>
                <div className="welcome-suggestions">
                  <p className="welcome-suggestions-label">
                    <Sparkles size={13} strokeWidth={2} />
                    Try asking
                  </p>
                  <div className="welcome-suggestions-grid">
                    {["Research the latest trends in AI agent frameworks",
                      "Review my Solidity smart contract for security issues",
                      "Reconcile all USDC invoices from last week",
                      "Analyse my portfolio and suggest rebalancing"
                    ].map((prompt) => (
                      <button
                        key={prompt}
                        type="button"
                        className="welcome-suggestion-chip"
                        onClick={() => handleSend(prompt)}
                      >
                        <span>{prompt}</span>
                        <ArrowRight size={12} strokeWidth={2} className="welcome-suggestion-arrow" />
                      </button>
                    ))}
                  </div>
                </div>
              </div>
            ) : (
              <>
                <div className="chat-messages-spacer" />
                {active.messages.map((m) => <MessageBubble key={m.id} message={m} agent={agent} />)}
                {isThinking && (
                  <div className="chat-msg agent">
                    <div className="chat-avatar">
                      <img src="/tesseris-logo.png" alt="TessFlow" style={{ width: 15, height: 15 }} />
                    </div>
                    <div className="chat-bubble">
                      <div className="chat-text">
                        <div className="typing-indicator">
                          <span className="typing-dot" /><span className="typing-dot" /><span className="typing-dot" />
                        </div>
                      </div>
                    </div>
                  </div>
                )}
                <div ref={btmRef} />
                {showScrollBtn && (
                  <button type="button" className="scroll-to-bottom-btn" onClick={() => { const el = messagesRef.current; if (el) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" }); }} aria-label="Scroll to bottom">
                    <ArrowDown size={14} strokeWidth={1.9} />
                  </button>
                )}
              </>
            )}
          </div>
          <ChatInput agent={active ? agent : undefined} onSend={handleSend} />
        </div>
      </div>

      {showPicker && (
        <AgentSelector agents={AGENT_CATALOG} installedAgentIds={installedAgents.map((a) => a.id)} onSelect={() => { mkConvo(); }} onClose={() => setShowPicker(false)} />
      )}
    </div>
  );
};

export default ChatPage;
