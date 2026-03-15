/**
 * WorkflowInspector — Right-side panel for node config and workflow info.
 */
import {
  Settings2, Zap, Wrench, Bot, GitBranch, ShieldCheck, Shuffle,
  ArrowRightFromLine, RefreshCw, Clock, CheckCircle2, Plug, AlertTriangle,
  FileText, ChevronRight,
} from "lucide-react";
import type { FlowNode, WorkflowDraft, FlowNodeConfig, ValidationIssue, NodeKind } from "../lib/types";

// ─── Helpers ─────────────────────────────────────────────────────────────────

const KIND_ICONS: Record<NodeKind, typeof Zap> = {
  trigger:   Zap,
  tool:      Wrench,
  agent:     Bot,
  condition: GitBranch,
  approval:  ShieldCheck,
  transform: Shuffle,
  output:    ArrowRightFromLine,
};

const KIND_ACCENTS: Record<NodeKind, string> = {
  trigger:   "#F59E0B",
  tool:      "#60A5FA",
  agent:     "#00CACC",
  condition: "#C084FC",
  approval:  "#34D399",
  transform: "#FB923C",
  output:    "#818CF8",
};

// ─── Props ───────────────────────────────────────────────────────────────────

interface WorkflowInspectorProps {
  draft: WorkflowDraft | null;
  selectedNode: FlowNode | null;
  validationIssues: ValidationIssue[];
  onUpdateNodeConfig: (nodeId: string, config: Partial<FlowNodeConfig>) => void;
  onUpdateNodeField: (nodeId: string, field: "title" | "description", value: string) => void;
}

// ─── Field component ─────────────────────────────────────────────────────────

function InspectorField({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="inspector-field">
      <label className="inspector-field-label">{label}</label>
      {children}
    </div>
  );
}

// ─── Node inspector ──────────────────────────────────────────────────────────

function NodeInspector({ node, onUpdateNodeConfig, onUpdateNodeField }: {
  node: FlowNode;
  onUpdateNodeConfig: (nodeId: string, config: Partial<FlowNodeConfig>) => void;
  onUpdateNodeField: (nodeId: string, field: "title" | "description", value: string) => void;
}) {
  const Icon = KIND_ICONS[node.kind] ?? Settings2;
  const accent = KIND_ACCENTS[node.kind] ?? "var(--accent-400)";
  const isDisconnected = node.config.authStatus === "disconnected";

  return (
    <div className="inspector-node-content">
      {/* Node identity */}
      <div className="inspector-node-header">
        <div className="inspector-node-icon" style={{ background: `${accent}14`, borderColor: `${accent}33`, color: accent }}>
          <Icon size={16} strokeWidth={2} />
        </div>
        <div>
          <div className="inspector-node-kind">{node.kind.charAt(0).toUpperCase() + node.kind.slice(1)} Node</div>
          <div className="inspector-node-id">ID: {node.id}</div>
        </div>
      </div>

      {/* Status */}
      <div className="inspector-status-row">
        <span className="inspector-status-label">Status</span>
        <span className={`inspector-status-value status-${node.status}`}>
          {node.status === "running" && <RefreshCw size={11} strokeWidth={2} className="spin" />}
          {node.status === "success" && <CheckCircle2 size={11} strokeWidth={2} />}
          {node.status === "idle"    && <Clock size={11} strokeWidth={2} />}
          {node.status}
        </span>
      </div>

      {/* Integration status */}
      {node.config.authStatus && node.config.authStatus !== "not_required" && (
        <div className="inspector-status-row">
          <span className="inspector-status-label">Integration</span>
          <span className={`inspector-status-value ${isDisconnected ? "status-error" : "status-success"}`}>
            {isDisconnected
              ? <AlertTriangle size={11} strokeWidth={2} />
              : <Plug size={11} strokeWidth={2} />
            }
            {isDisconnected ? "Disconnected" : "Connected"}
          </span>
        </div>
      )}

      <div className="inspector-divider" />

      {/* Edit fields */}
      <InspectorField label="Title">
        <input
          className="inspector-input"
          value={node.title}
          onChange={(e) => onUpdateNodeField(node.id, "title", e.target.value)}
        />
      </InspectorField>

      <InspectorField label="Description">
        <textarea
          className="inspector-input inspector-textarea"
          value={node.description}
          onChange={(e) => onUpdateNodeField(node.id, "description", e.target.value)}
          rows={2}
        />
      </InspectorField>

      {node.config.provider !== undefined && (
        <InspectorField label="Provider">
          <input
            className="inspector-input"
            value={node.config.provider ?? ""}
            onChange={(e) => onUpdateNodeConfig(node.id, { provider: e.target.value })}
          />
        </InspectorField>
      )}

      {node.config.tool !== undefined && (
        <InspectorField label="Tool / Action">
          <input
            className="inspector-input"
            value={node.config.tool ?? ""}
            onChange={(e) => onUpdateNodeConfig(node.id, { tool: e.target.value })}
          />
        </InspectorField>
      )}

      {/* Trigger-specific */}
      {node.kind === "trigger" && (
        <InspectorField label="Schedule (cron)">
          <input
            className="inspector-input inspector-mono"
            value={node.config.schedule ?? ""}
            onChange={(e) => onUpdateNodeConfig(node.id, { schedule: e.target.value })}
            placeholder="*/5 * * * *"
          />
        </InspectorField>
      )}

      {/* Condition-specific */}
      {node.kind === "condition" && (
        <InspectorField label="Condition Expression">
          <input
            className="inspector-input inspector-mono"
            value={node.config.conditionExpression ?? ""}
            onChange={(e) => onUpdateNodeConfig(node.id, { conditionExpression: e.target.value })}
            placeholder="value > threshold"
          />
        </InspectorField>
      )}

      {/* Retry / Timeout */}
      {(node.kind === "tool" || node.kind === "agent") && (
        <div className="inspector-row-2col">
          <InspectorField label="Retry Count">
            <input
              className="inspector-input"
              type="number"
              min={0}
              max={10}
              value={node.config.retryCount ?? 1}
              onChange={(e) => onUpdateNodeConfig(node.id, { retryCount: Number(e.target.value) })}
            />
          </InspectorField>
          <InspectorField label="Timeout (s)">
            <input
              className="inspector-input"
              type="number"
              min={1}
              value={node.config.timeout ?? 30}
              onChange={(e) => onUpdateNodeConfig(node.id, { timeout: Number(e.target.value) })}
            />
          </InspectorField>
        </div>
      )}

      {/* Approval toggle */}
      {(node.kind === "approval" || node.kind === "output") && (
        <InspectorField label="Approval Required">
          <label className="inspector-toggle-row">
            <input
              type="checkbox"
              className="inspector-checkbox"
              checked={node.config.approvalRequired ?? false}
              onChange={(e) => onUpdateNodeConfig(node.id, { approvalRequired: e.target.checked })}
            />
            <span>Require human approval before proceeding</span>
          </label>
        </InspectorField>
      )}

      {/* Notes */}
      <InspectorField label="Notes">
        <textarea
          className="inspector-input inspector-textarea"
          value={node.config.notes ?? ""}
          placeholder="Add notes about this node..."
          onChange={(e) => onUpdateNodeConfig(node.id, { notes: e.target.value })}
          rows={2}
        />
      </InspectorField>

      {/* Error details */}
      {node.error && (
        <div className="inspector-error-box">
          <AlertTriangle size={13} strokeWidth={2} />
          <span>{node.error}</span>
        </div>
      )}
    </div>
  );
}

// ─── Workflow overview ────────────────────────────────────────────────────────

function WorkflowOverview({ draft, validationIssues }: {
  draft: WorkflowDraft;
  validationIssues: ValidationIssue[];
}) {
  const errors   = validationIssues.filter((i) => i.severity === "error");
  const warnings = validationIssues.filter((i) => i.severity === "warning");

  return (
    <div className="inspector-overview">
      <div className="inspector-overview-header">
        <FileText size={16} strokeWidth={1.8} style={{ color: "var(--accent-400)" }} />
        <div>
          <div className="inspector-overview-name">{draft.name}</div>
          <div className="inspector-overview-id">ID: {draft.id.slice(0, 20)}...</div>
        </div>
      </div>

      <p className="inspector-overview-desc">{draft.description}</p>

      {/* Stats */}
      <div className="inspector-stats">
        <div className="inspector-stat">
          <span className="inspector-stat-value">{draft.nodes.length}</span>
          <span className="inspector-stat-label">Nodes</span>
        </div>
        <div className="inspector-stat">
          <span className="inspector-stat-value">{draft.edges.length}</span>
          <span className="inspector-stat-label">Edges</span>
        </div>
        <div className="inspector-stat">
          <span className="inspector-stat-value" style={{ color: errors.length > 0 ? "#FCA5A5" : warnings.length > 0 ? "#FCD34D" : "#4ADE80" }}>
            {validationIssues.length}
          </span>
          <span className="inspector-stat-label">Issues</span>
        </div>
      </div>

      <div className="inspector-divider" />

      {/* Assumptions */}
      {draft.assumptions.length > 0 && (
        <div className="inspector-section">
          <div className="inspector-section-title">Assumptions</div>
          <ul className="inspector-list">
            {draft.assumptions.map((a, i) => (
              <li key={i}>
                <ChevronRight size={10} strokeWidth={2} style={{ color: "var(--accent-400)", flexShrink: 0 }} />
                {a}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Unresolved fields */}
      {draft.unresolvedFields.length > 0 && (
        <div className="inspector-section">
          <div className="inspector-section-title" style={{ color: "#FCD34D" }}>
            <AlertTriangle size={12} strokeWidth={2} style={{ color: "#FCD34D" }} />
            Unresolved Fields
          </div>
          <ul className="inspector-list inspector-list-warn">
            {draft.unresolvedFields.map((f, i) => (
              <li key={i}>
                <ChevronRight size={10} strokeWidth={2} style={{ color: "#FCD34D", flexShrink: 0 }} />
                {f}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Validation issues */}
      {validationIssues.length > 0 && (
        <div className="inspector-section">
          <div className="inspector-section-title">Validation</div>
          <div className="inspector-issues">
            {validationIssues.map((issue) => (
              <div key={issue.id} className={`inspector-issue svi-${issue.severity}`}>
                {issue.message}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="inspector-section">
        <div className="inspector-section-title">Select a node</div>
        <p className="inspector-select-hint">Click any node on the canvas to view and edit its configuration.</p>
      </div>
    </div>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

const WorkflowInspector = ({
  draft,
  selectedNode,
  validationIssues,
  onUpdateNodeConfig,
  onUpdateNodeField,
}: WorkflowInspectorProps) => {
  return (
    <div className="studio-inspector">
      <div className="studio-inspector-header">
        <Settings2 size={16} strokeWidth={1.8} style={{ color: "var(--accent-400)" }} />
        <span className="studio-inspector-title">
          {selectedNode ? selectedNode.title : "Inspector"}
        </span>
      </div>

      <div className="studio-inspector-body">
        {!draft ? (
          <div className="inspector-empty">
            <Settings2 size={28} strokeWidth={1.2} style={{ color: "var(--text-dim)", opacity: 0.4 }} />
            <p>No workflow loaded.<br />Generate one from the chat panel.</p>
          </div>
        ) : selectedNode ? (
          <NodeInspector
            node={selectedNode}
            onUpdateNodeConfig={onUpdateNodeConfig}
            onUpdateNodeField={onUpdateNodeField}
          />
        ) : (
          <WorkflowOverview draft={draft} validationIssues={validationIssues} />
        )}
      </div>
    </div>
  );
};

export default WorkflowInspector;
