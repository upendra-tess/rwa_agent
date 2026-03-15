/**
 * WorkflowNode — Unified custom node for all workflow node kinds.
 * Renders with the native TessFlow visual style and status indicators.
 */
import { memo } from "react";
import { Handle, Position, type NodeProps } from "@xyflow/react";
import {
  Zap, Wrench, Bot, GitBranch, ShieldCheck, Shuffle, Send,
  CheckCircle2, XCircle, Loader, Clock, AlertTriangle, Plug,
} from "lucide-react";
import type { NodeKind, NodeStatus, FlowNodeConfig } from "../../lib/types";

// ─── Node kind → icon / accent ──────────────────────────────────────────────

interface KindStyle {
  icon: typeof Zap;
  label: string;
  accent: string;
  accentLight: string;
  bg: string;
  border: string;
}

const KIND_STYLES: Record<NodeKind, KindStyle> = {
  trigger: {
    icon: Zap,
    label: "Trigger",
    accent: "#00F8FA",
    accentLight: "#A5F3FC",
    bg: "rgba(0,248,250,0.06)",
    border: "rgba(0,248,250,0.18)",
  },
  tool: {
    icon: Wrench,
    label: "Tool",
    accent: "#60A5FA",
    accentLight: "#93C5FD",
    bg: "rgba(96,165,250,0.06)",
    border: "rgba(96,165,250,0.18)",
  },
  agent: {
    icon: Bot,
    label: "Agent",
    accent: "#C084FC",
    accentLight: "#D8B4FE",
    bg: "rgba(192,132,252,0.06)",
    border: "rgba(192,132,252,0.18)",
  },
  condition: {
    icon: GitBranch,
    label: "Condition",
    accent: "#F59E0B",
    accentLight: "#FCD34D",
    bg: "rgba(245,158,11,0.06)",
    border: "rgba(245,158,11,0.18)",
  },
  approval: {
    icon: ShieldCheck,
    label: "Approval",
    accent: "#34D399",
    accentLight: "#6EE7B7",
    bg: "rgba(52,211,153,0.06)",
    border: "rgba(52,211,153,0.18)",
  },
  transform: {
    icon: Shuffle,
    label: "Transform",
    accent: "#94A3B8",
    accentLight: "#CBD5E1",
    bg: "rgba(148,163,184,0.06)",
    border: "rgba(148,163,184,0.18)",
  },
  output: {
    icon: Send,
    label: "Output",
    accent: "#818CF8",
    accentLight: "#A5B4FC",
    bg: "rgba(129,140,248,0.06)",
    border: "rgba(129,140,248,0.18)",
  },
};

interface StatusStyle {
  icon: typeof CheckCircle2;
  color: string;
  glow?: string;
  animate?: boolean;
}

const STATUS_STYLES: Record<NodeStatus, StatusStyle> = {
  idle:    { icon: Clock,        color: "var(--text-dim)" },
  running: { icon: Loader,       color: "#00F8FA", glow: "0 0 8px rgba(0,248,250,0.4)", animate: true },
  waiting: { icon: ShieldCheck,  color: "#FCD34D", glow: "0 0 6px rgba(245,158,11,0.3)" },
  success: { icon: CheckCircle2, color: "#4ADE80" },
  error:   { icon: XCircle,      color: "#FCA5A5" },
};

// ─── Data shape for React Flow ───────────────────────────────────────────────

export interface WorkflowNodeData {
  kind: NodeKind;
  title: string;
  description: string;
  status: NodeStatus;
  config?: FlowNodeConfig;
  error?: string;
  isSelected?: boolean;
  [key: string]: unknown;
}

// ─── Component ───────────────────────────────────────────────────────────────

const WorkflowNode = memo(({ data }: NodeProps) => {
  const nodeData = data as unknown as WorkflowNodeData;
  const kindStyle = KIND_STYLES[nodeData.kind] ?? KIND_STYLES.tool;
  const statusStyle = STATUS_STYLES[nodeData.status] ?? STATUS_STYLES.idle;
  
  const KindIcon = kindStyle.icon;
  const StatusIcon = statusStyle.icon;
  
  const isRunning = nodeData.status === "running";
  const isWaiting = nodeData.status === "waiting";
  const isError = nodeData.status === "error";
  const isSuccess = nodeData.status === "success";
  const isSelected = nodeData.isSelected;
  
  const provider = nodeData.config?.provider;
  const tool = nodeData.config?.tool;
  const authStatus = nodeData.config?.authStatus;
  const isDisconnected = authStatus === "disconnected";
  const isConnected = authStatus === "connected";

  // Compute dynamic border/shadow
  const getBorderColor = () => {
    if (isSelected) return kindStyle.accent;
    if (isError) return "rgba(239,68,68,0.5)";
    if (isRunning) return "rgba(0,248,250,0.4)";
    if (isWaiting) return "rgba(245,158,11,0.4)";
    if (isSuccess) return "rgba(34,197,94,0.3)";
    return "rgba(255,255,255,0.08)";
  };

  const getBoxShadow = () => {
    if (isSelected) return `0 0 0 2px ${kindStyle.accent}40, 0 8px 24px rgba(0,0,0,0.25)`;
    if (isRunning) return "0 0 20px rgba(0,248,250,0.15), 0 6px 20px rgba(0,0,0,0.2)";
    if (isWaiting) return "0 0 16px rgba(245,158,11,0.12), 0 6px 20px rgba(0,0,0,0.2)";
    if (isError) return "0 0 16px rgba(239,68,68,0.12), 0 6px 20px rgba(0,0,0,0.2)";
    return "0 4px 16px rgba(0,0,0,0.18)";
  };

  return (
    <div
      className={`wf-node ${isSelected ? "selected" : ""}`}
      style={{
        borderColor: getBorderColor(),
        boxShadow: getBoxShadow(),
        background: isRunning 
          ? "linear-gradient(145deg, rgba(11,17,22,0.96), rgba(0,40,42,0.25))"
          : undefined,
      }}
    >
      {/* Handles */}
      <Handle type="target" position={Position.Top} className="wf-handle" />
      <Handle type="source" position={Position.Bottom} className="wf-handle" />

      {/* Header row */}
      <div className="wf-node-header">
        <div
          className="wf-node-icon"
          style={{
            background: kindStyle.bg,
            borderColor: kindStyle.border,
            color: kindStyle.accent,
          }}
        >
          <KindIcon size={13} strokeWidth={2.2} />
        </div>

        <div className="wf-node-titles">
          <span className="wf-node-title">{nodeData.title}</span>
          <span
            className="wf-node-badge"
            style={{
              background: kindStyle.bg,
              color: kindStyle.accent,
              borderColor: kindStyle.border,
            }}
          >
            {kindStyle.label}
          </span>
        </div>

        <div
          className="wf-node-status"
          style={{ filter: statusStyle.glow ? `drop-shadow(${statusStyle.glow})` : undefined }}
        >
          <StatusIcon
            size={15}
            strokeWidth={2}
            style={{ color: statusStyle.color }}
            className={statusStyle.animate ? "spin" : ""}
          />
        </div>
      </div>

      {/* Description */}
      {nodeData.description && (
        <p className="wf-node-desc">{nodeData.description}</p>
      )}

      {/* Provider / tool row */}
      {provider && (
        <div className="wf-node-provider">
          {isDisconnected && (
            <AlertTriangle size={11} strokeWidth={2.2} style={{ color: "#FCD34D" }} />
          )}
          {isConnected && (
            <Plug size={11} strokeWidth={2.2} style={{ color: "#4ADE80" }} />
          )}
          <span>{provider}</span>
          {tool && <span className="wf-node-tool">· {tool}</span>}
        </div>
      )}

      {/* Error message */}
      {isError && nodeData.error && (
        <div className="wf-node-error">
          <XCircle size={11} strokeWidth={2.2} />
          <span>{nodeData.error}</span>
        </div>
      )}
    </div>
  );
});

WorkflowNode.displayName = "WorkflowNode";
export default WorkflowNode;
