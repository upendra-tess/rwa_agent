/**
 * WorkflowToolbar — Top action bar above the canvas/inspector area.
 * Shows draft status, validate/run/save/reset buttons, and workflow name.
 */
import {
  CheckCircle2, Play, Save, RotateCcw, AlertTriangle,
  Loader, XCircle, Clock, Zap, Shield, CheckCheck,
} from "lucide-react";
import type { WorkflowStatus, ExecutionStatus } from "../lib/types";

// ─── Props ───────────────────────────────────────────────────────────────────

interface WorkflowToolbarProps {
  workflowName: string;
  workflowStatus: WorkflowStatus;
  executionStatus: ExecutionStatus;
  issueCount: number;
  isValidating: boolean;
  onValidate: () => void;
  onRun: () => void;
  onSaveDraft: () => void;
  onReset: () => void;
  disabled: boolean;
}

// ─── Status badge ─────────────────────────────────────────────────────────────

interface StatusConfig {
  label: string;
  color: string;
  bg: string;
  border: string;
  icon: typeof CheckCircle2;
  spin?: boolean;
}

const WORKFLOW_STATUS_CONFIG: Record<WorkflowStatus, StatusConfig> = {
  idle:                { label: "Idle",       color: "var(--text-dim)",    bg: "rgba(255,255,255,0.03)", border: "var(--border-soft)", icon: Clock },
  draft:               { label: "Draft",      color: "#7CB8F8",            bg: "rgba(96,165,250,0.07)",  border: "rgba(96,165,250,0.18)", icon: Zap },
  resolving:           { label: "Resolving",  color: "#00CACC",            bg: "rgba(0,202,204,0.07)",   border: "rgba(0,202,204,0.18)", icon: Loader, spin: true },
  needs_input:         { label: "Needs Input",color: "#FCD34D",            bg: "rgba(245,158,11,0.07)",  border: "rgba(245,158,11,0.18)", icon: AlertTriangle },
  ready:               { label: "Ready",      color: "#4ADE80",            bg: "rgba(34,197,94,0.07)",   border: "rgba(34,197,94,0.18)", icon: CheckCircle2 },
  running:             { label: "Running",    color: "#00F8FA",            bg: "rgba(0,248,250,0.07)",   border: "rgba(0,248,250,0.18)", icon: Loader, spin: true },
  paused_for_approval: { label: "Approval",   color: "#FCD34D",            bg: "rgba(245,158,11,0.07)",  border: "rgba(245,158,11,0.18)", icon: Shield },
  completed:           { label: "Completed",  color: "#4ADE80",            bg: "rgba(34,197,94,0.07)",   border: "rgba(34,197,94,0.18)", icon: CheckCheck },
  failed:              { label: "Failed",     color: "#FCA5A5",            bg: "rgba(239,68,68,0.07)",   border: "rgba(239,68,68,0.18)", icon: XCircle },
};

function WorkflowStatusBadge({ status }: { status: WorkflowStatus }) {
  const cfg = WORKFLOW_STATUS_CONFIG[status] ?? WORKFLOW_STATUS_CONFIG.idle;
  const Icon = cfg.icon;

  return (
    <div
      className="wf-toolbar-status-badge"
      style={{ color: cfg.color, background: cfg.bg, borderColor: cfg.border }}
    >
      <Icon size={11} strokeWidth={2} className={cfg.spin ? "spin" : ""} />
      <span>{cfg.label}</span>
    </div>
  );
}

// ─── Component ───────────────────────────────────────────────────────────────

const WorkflowToolbar = ({
  workflowName,
  workflowStatus,
  executionStatus,
  issueCount,
  isValidating,
  onValidate,
  onRun,
  onSaveDraft,
  onReset,
  disabled,
}: WorkflowToolbarProps) => {
  const isRunning = executionStatus === "running" || workflowStatus === "running";
  const canRun = !disabled && !isRunning && workflowStatus !== "idle";

  return (
    <div className="wf-toolbar">
      {/* Left: workflow name + status */}
      <div className="wf-toolbar-left">
        <div className="wf-toolbar-name">
          {workflowName || "Untitled Workflow"}
        </div>
        <WorkflowStatusBadge status={workflowStatus} />
        {issueCount > 0 && (
          <div className="wf-toolbar-issues">
            <AlertTriangle size={11} strokeWidth={2} style={{ color: "#FCD34D" }} />
            <span>{issueCount} issue{issueCount !== 1 ? "s" : ""}</span>
          </div>
        )}
      </div>

      {/* Right: actions */}
      <div className="wf-toolbar-actions">
        {/* Validate */}
        <button
          type="button"
          className="tf-btn secondary"
          onClick={onValidate}
          disabled={disabled || isValidating}
          title="Validate workflow"
        >
          {isValidating
            ? <Loader size={14} strokeWidth={2} className="spin" />
            : <CheckCircle2 size={14} strokeWidth={2} />
          }
          {isValidating ? "Validating…" : "Validate"}
        </button>

        {/* Run */}
        <button
          type="button"
          className="tf-btn accent"
          onClick={onRun}
          disabled={!canRun}
          title="Run workflow simulation"
        >
          {isRunning
            ? <Loader size={14} strokeWidth={2} className="spin" />
            : <Play size={14} strokeWidth={2} />
          }
          {isRunning ? "Running…" : "Run"}
        </button>

        {/* Save */}
        <button
          type="button"
          className="tf-btn secondary"
          onClick={onSaveDraft}
          disabled={disabled}
          title="Save draft"
        >
          <Save size={14} strokeWidth={2} />
          Save
        </button>

        {/* Reset */}
        <button
          type="button"
          className="tf-btn ghost"
          onClick={onReset}
          title="Reset workflow"
        >
          <RotateCcw size={14} strokeWidth={2} />
          Reset
        </button>
      </div>
    </div>
  );
};

export default WorkflowToolbar;
