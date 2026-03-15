/**
 * WorkflowChatPanel — Left-side chat surface for the workflow studio.
 * Handles user prompts, assistant responses, workflow proposals,
 * validation summaries, and execution event cards.
 */
import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send, Sparkles, CheckCircle2, XCircle, AlertTriangle,
  Loader, PlayCircle, ShieldCheck, Info, Bot, User,
  ChevronRight, RefreshCw,
} from "lucide-react";
import type { StudioChatMessage, ExecutionEvent } from "../lib/types";
import { DEMO_PROMPTS } from "../lib/mockOrchestrator";

// ─── Props ───────────────────────────────────────────────────────────────────

interface WorkflowChatPanelProps {
  messages: StudioChatMessage[];
  isGenerating: boolean;
  hasWorkflow: boolean;
  onSubmitPrompt: (prompt: string) => void;
  onOpenCanvas: () => void;
  onValidate: () => void;
  onRun: () => void;
}

// ─── Execution event card ────────────────────────────────────────────────────

function ExecutionEventCard({ event }: { event: ExecutionEvent }) {
  const config: Record<string, { icon: typeof CheckCircle2; color: string; bg: string }> = {
    started:              { icon: PlayCircle,    color: "#00F8FA", bg: "rgba(0,248,250,0.06)" },
    node_started:         { icon: Loader,        color: "#00CACC", bg: "rgba(0,202,204,0.06)" },
    node_completed:       { icon: CheckCircle2,  color: "#4ADE80", bg: "rgba(34,197,94,0.06)" },
    node_failed:          { icon: XCircle,       color: "#FCA5A5", bg: "rgba(239,68,68,0.06)" },
    waiting_for_approval: { icon: ShieldCheck,   color: "#FCD34D", bg: "rgba(245,158,11,0.06)" },
    approval_granted:     { icon: CheckCircle2,  color: "#4ADE80", bg: "rgba(34,197,94,0.06)" },
    completed:            { icon: CheckCircle2,  color: "#4ADE80", bg: "rgba(34,197,94,0.08)" },
    failed:               { icon: XCircle,       color: "#FCA5A5", bg: "rgba(239,68,68,0.08)" },
  };

  const cfg = config[event.type] ?? config.node_started;
  const Icon = cfg.icon;
  const isRunning = event.type === "node_started";

  return (
    <div className="studio-event-card" style={{ background: cfg.bg, borderColor: `${cfg.color}22` }}>
      <Icon size={13} strokeWidth={2} style={{ color: cfg.color, flexShrink: 0 }} className={isRunning ? "spin" : ""} />
      <span className="studio-event-msg">{event.message}</span>
      <span className="studio-event-time">
        {new Date(event.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
      </span>
    </div>
  );
}

// ─── Workflow proposal card ───────────────────────────────────────────────────

interface ProposalCardProps {
  summary: string;
  assumptions: string[];
  unresolvedFields: string[];
  onOpenCanvas: () => void;
  onValidate: () => void;
  onRun: () => void;
}

function WorkflowProposalCard({ summary, assumptions, unresolvedFields, onOpenCanvas, onValidate, onRun }: ProposalCardProps) {
  return (
    <div className="studio-proposal-card">
      <div className="studio-proposal-header">
        <Sparkles size={14} strokeWidth={2} style={{ color: "var(--accent-300)" }} />
        <span>Workflow Generated</span>
      </div>
      <p className="studio-proposal-summary">{summary}</p>

      {assumptions.length > 0 && (
        <div className="studio-proposal-section">
          <span className="studio-proposal-section-label">Assumptions</span>
          <ul className="studio-proposal-list">
            {assumptions.map((a, i) => (
              <li key={i}>{a}</li>
            ))}
          </ul>
        </div>
      )}

      {unresolvedFields.length > 0 && (
        <div className="studio-proposal-section">
          <div className="studio-proposal-unresolved-label">
            <AlertTriangle size={11} strokeWidth={2} style={{ color: "#FCD34D" }} />
            <span>Needs input</span>
          </div>
          <ul className="studio-proposal-list studio-proposal-list-warn">
            {unresolvedFields.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="studio-proposal-actions">
        <button type="button" className="tf-btn primary tiny" onClick={onOpenCanvas}>
          <ChevronRight size={13} strokeWidth={2} />
          Open in Canvas
        </button>
        <button type="button" className="tf-btn secondary tiny" onClick={onValidate}>
          Validate
        </button>
        <button type="button" className="tf-btn secondary tiny" onClick={onRun}>
          Run
        </button>
      </div>
    </div>
  );
}

// ─── Validation summary card ──────────────────────────────────────────────────

function ValidationSummaryCard({ msg }: { msg: StudioChatMessage }) {
  const result = msg.validationResult;
  if (!result) return null;

  const errors   = result.issues.filter((i) => i.severity === "error");
  const warnings = result.issues.filter((i) => i.severity === "warning");
  const infos    = result.issues.filter((i) => i.severity === "info");

  return (
    <div className={`studio-validation-card ${result.valid ? "valid" : "invalid"}`}>
      <div className="studio-validation-header">
        {result.valid
          ? <CheckCircle2 size={14} strokeWidth={2} style={{ color: "#4ADE80" }} />
          : <AlertTriangle size={14} strokeWidth={2} style={{ color: "#FCD34D" }} />
        }
        <span>{result.valid ? "Validation passed" : "Validation issues found"}</span>
        <span className="studio-validation-count">{result.issues.length} issue{result.issues.length !== 1 ? "s" : ""}</span>
      </div>

      {result.issues.length > 0 && (
        <ul className="studio-validation-list">
          {[...errors, ...warnings, ...infos].map((issue) => (
            <li key={issue.id} className={`studio-validation-issue svi-${issue.severity}`}>
              {issue.severity === "error"   && <XCircle      size={10} strokeWidth={2} />}
              {issue.severity === "warning" && <AlertTriangle size={10} strokeWidth={2} />}
              {issue.severity === "info"    && <Info          size={10} strokeWidth={2} />}
              <span>{issue.message}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ─── Message renderer ─────────────────────────────────────────────────────────

function ChatMessageItem({ msg, onOpenCanvas, onValidate, onRun }: {
  msg: StudioChatMessage;
  onOpenCanvas: () => void;
  onValidate: () => void;
  onRun: () => void;
}) {
  if (msg.kind === "system_notice") {
    return (
      <div className="studio-chat-system">
        <span>{msg.text}</span>
      </div>
    );
  }

  if (msg.kind === "user") {
    return (
      <div className="studio-chat-row user">
        <div className="studio-chat-avatar user-avatar">
          <User size={14} strokeWidth={1.8} />
        </div>
        <div className="studio-chat-bubble user-bubble">
          <p>{msg.text}</p>
        </div>
      </div>
    );
  }

  if (msg.kind === "workflow_proposal") {
    return (
      <div className="studio-chat-row assistant">
        <div className="studio-chat-avatar">
          <Bot size={14} strokeWidth={1.8} />
        </div>
        <div className="studio-chat-bubble">
          {msg.text && <p className="studio-assistant-text">{msg.text}</p>}
          {msg.workflowSummary && (
            <WorkflowProposalCard
              summary={msg.workflowSummary}
              assumptions={msg.assumptions ?? []}
              unresolvedFields={msg.unresolvedFields ?? []}
              onOpenCanvas={onOpenCanvas}
              onValidate={onValidate}
              onRun={onRun}
            />
          )}
        </div>
      </div>
    );
  }

  if (msg.kind === "validation_summary") {
    return (
      <div className="studio-chat-row assistant">
        <div className="studio-chat-avatar">
          <Bot size={14} strokeWidth={1.8} />
        </div>
        <div className="studio-chat-bubble">
          <ValidationSummaryCard msg={msg} />
        </div>
      </div>
    );
  }

  if (msg.kind === "execution_event" && msg.executionEvent) {
    return <ExecutionEventCard event={msg.executionEvent} />;
  }

  if (msg.kind === "approval_request") {
    return (
      <div className="studio-chat-row assistant">
        <div className="studio-chat-avatar">
          <ShieldCheck size={14} strokeWidth={1.8} style={{ color: "#FCD34D" }} />
        </div>
        <div className="studio-chat-bubble">
          <div className="studio-approval-card">
            <AlertTriangle size={14} strokeWidth={2} style={{ color: "#FCD34D" }} />
            <span>{msg.text}</span>
          </div>
        </div>
      </div>
    );
  }

  // assistant_text default
  return (
    <div className="studio-chat-row assistant">
      <div className="studio-chat-avatar">
        <Bot size={14} strokeWidth={1.8} />
      </div>
      <div className="studio-chat-bubble">
        <p className="studio-assistant-text">{msg.text}</p>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

const WorkflowChatPanel = ({
  messages,
  isGenerating,
  hasWorkflow,
  onSubmitPrompt,
  onOpenCanvas,
  onValidate,
  onRun,
}: WorkflowChatPanelProps) => {
  const [input, setInput] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
  }, [messages, isGenerating]);

  const handleSubmit = useCallback(() => {
    const trimmed = input.trim();
    if (!trimmed || isGenerating) return;
    onSubmitPrompt(trimmed);
    setInput("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  }, [input, isGenerating, onSubmitPrompt]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    // Auto-resize
    const ta = e.target;
    ta.style.height = "auto";
    ta.style.height = `${Math.min(ta.scrollHeight, 120)}px`;
  };

  const isEmpty = messages.length === 0;

  return (
    <div className="studio-chat-panel">
      {/* Header */}
      <div className="studio-chat-header">
        <div className="studio-chat-header-icon">
          <Bot size={16} strokeWidth={1.8} />
        </div>
        <div>
          <div className="studio-chat-header-title">Workflow Assistant</div>
          <div className="studio-chat-header-sub">Describe your automation</div>
        </div>
        {hasWorkflow && (
          <button type="button" className="studio-chat-reset-btn" onClick={onOpenCanvas} title="Focus canvas">
            <RefreshCw size={13} strokeWidth={2} />
          </button>
        )}
      </div>

      {/* Message thread */}
      <div className="studio-chat-messages">
        {isEmpty && !isGenerating ? (
          <div className="studio-chat-welcome">
            <div className="studio-chat-welcome-icon">
              <Sparkles size={28} strokeWidth={1.4} />
            </div>
            <h4>Start with a prompt</h4>
            <p>Describe what you want to automate and the AI will generate a visual workflow for you.</p>
            <div className="studio-chat-suggestions-label">Try an example</div>
            <div className="studio-chat-suggestions">
              {DEMO_PROMPTS.map((p, i) => (
                <button
                  key={i}
                  type="button"
                  className="studio-chat-suggestion-chip"
                  onClick={() => onSubmitPrompt(p)}
                >
                  <ChevronRight size={12} strokeWidth={2} style={{ color: "var(--accent-400)", flexShrink: 0 }} />
                  <span>{p}</span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((msg) => (
              <ChatMessageItem
                key={msg.id}
                msg={msg}
                onOpenCanvas={onOpenCanvas}
                onValidate={onValidate}
                onRun={onRun}
              />
            ))}
            {isGenerating && (
              <div className="studio-chat-row assistant">
                <div className="studio-chat-avatar">
                  <Bot size={14} strokeWidth={1.8} />
                </div>
                <div className="studio-chat-bubble">
                  <div className="studio-typing">
                    <span /><span /><span />
                  </div>
                </div>
              </div>
            )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Composer */}
      <div className="studio-chat-composer">
        {hasWorkflow && (
          <div className="studio-chat-composer-hint">
            Tip: Type follow-up edits like "add approval before output" or "replace Telegram with Discord"
          </div>
        )}
        <div className={`studio-chat-input-wrap ${input ? "has-content" : ""}`}>
          <textarea
            ref={textareaRef}
            className="studio-chat-input"
            placeholder={hasWorkflow ? "Edit the workflow..." : "Describe your automation workflow..."}
            value={input}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            disabled={isGenerating}
            rows={1}
          />
          <button
            type="button"
            className="studio-chat-send-btn"
            onClick={handleSubmit}
            disabled={!input.trim() || isGenerating}
            aria-label="Send"
          >
            {isGenerating
              ? <Loader size={15} strokeWidth={2} className="spin" />
              : <Send size={15} strokeWidth={2} />
            }
          </button>
        </div>
        <div className="studio-chat-composer-meta">
          <span>Enter to send · Shift+Enter for new line</span>
        </div>
      </div>
    </div>
  );
};

export default WorkflowChatPanel;
