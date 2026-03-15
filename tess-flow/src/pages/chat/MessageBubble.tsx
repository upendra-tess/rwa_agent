import { User } from "lucide-react";
import { ConversationMessage, Agent, AgentRun, RunStep } from "../../types";
import AgentIcon from "../../shared/AgentIcon";
import { CheckCircle2, Loader, XCircle, Clock } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { AGENT_CATALOG } from "../../data/catalog";

interface MessageBubbleProps {
  message: ConversationMessage;
  agent?: Agent;
}

const StepIcon = ({ status }: { status: RunStep["status"] }) => {
  if (status === "done") return <CheckCircle2 size={12} className="inline-step-done" color="var(--accent-400)" />;
  if (status === "running") return <Loader size={12} className="inline-step-running spin" color="var(--accent-400)" />;
  if (status === "error") return <XCircle size={12} className="inline-step-error" color="var(--error)" />;
  return <Clock size={12} className="inline-step-pending" color="var(--text-dim)" />;
};

const RunCard = ({ run }: { run: AgentRun }) => {
  const done = run.steps.filter((s) => s.status === "done").length;
  const total = run.steps.length;
  const pct = total > 0 ? (done / total) * 100 : 0;

  return (
    <div className={`inline-run-card status-${run.status}`}>
      <div className="inline-steps">
        {run.steps.map((s) => (
          <div key={s.id} className={`inline-step status-${s.status}`}>
            <StepIcon status={s.status} />
            <span className="inline-step-label">{s.label}</span>
          </div>
        ))}
      </div>
      {run.status === "running" && (
        <div className="inline-run-progress-wrap">
          <div className="inline-run-progress-bar">
            <div className="inline-run-progress-fill" style={{ width: `${pct}%` }} />
          </div>
          <span className="inline-run-progress-label">{done}/{total}</span>
        </div>
      )}
    </div>
  );
};

const fmtTime = (iso: string) => {
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
};

const MessageBubble = ({ message }: MessageBubbleProps) => {
  if (message.role === "system") {
    return (
      <div className="chat-msg system">
        <span className="chat-system-text">{message.text}</span>
      </div>
    );
  }

  const isUser = message.role === "user";
  const isRunCard = message.type === "run-card" || message.type === "run-complete";
  
  // Get the agent from the run data if available
  const responseAgent = message.run 
    ? AGENT_CATALOG.find(a => a.id === message.run!.agentId)
    : undefined;

  return (
    <div className={`chat-msg ${isUser ? "user" : "agent"}`}>
      <div className="chat-avatar">
        {isUser ? (
          <User size={13} />
        ) : responseAgent ? (
          <AgentIcon name={responseAgent.iconName} size={15} />
        ) : (
          <img src="/tesseris-logo.png" alt="TessFlow" style={{ width: '15px', height: '15px' }} />
        )}
      </div>

      <div className="chat-bubble">
        {!isUser && responseAgent && (
          <div style={{ 
            fontSize: '10px', 
            color: 'var(--text-dim)', 
            marginBottom: '4px',
            fontWeight: 600,
            letterSpacing: '0.02em'
          }}>
            {responseAgent.name}
          </div>
        )}
        <div className="chat-text">
          {message.text && (
            isUser ? (
              <p>{message.text}</p>
            ) : (
              <div className="chat-markdown">
                <ReactMarkdown>{message.text}</ReactMarkdown>
              </div>
            )
          )}
          {isRunCard && message.run && <RunCard run={message.run} />}
        </div>
        <div className="chat-time">{fmtTime(message.timestamp)}</div>
      </div>
    </div>
  );
};

export default MessageBubble;
