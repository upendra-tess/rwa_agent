/**
 * TessFlow Studio — Core type definitions.
 * Single source of truth for all workflow studio domain types.
 */

// ─── Workflow Status ─────────────────────────────────────────────────────────

export type WorkflowStatus =
  | "idle"
  | "draft"
  | "resolving"
  | "needs_input"
  | "ready"
  | "running"
  | "paused_for_approval"
  | "completed"
  | "failed";

export type NodeStatus =
  | "idle"
  | "running"
  | "waiting"
  | "success"
  | "error";

export type NodeKind =
  | "trigger"
  | "tool"
  | "agent"
  | "condition"
  | "approval"
  | "transform"
  | "output";

// ─── Workflow Graph ──────────────────────────────────────────────────────────

export interface FlowNodeConfig {
  provider?: string;
  tool?: string;
  inputs?: Record<string, string>;
  outputs?: string[];
  retryCount?: number;
  timeout?: number;
  approvalRequired?: boolean;
  schedule?: string;
  conditionExpression?: string;
  conditionTrueBranch?: string;
  conditionFalseBranch?: string;
  authStatus?: "connected" | "disconnected" | "not_required";
  notes?: string;
}

export interface FlowNode {
  id: string;
  kind: NodeKind;
  title: string;
  description: string;
  status: NodeStatus;
  config: FlowNodeConfig;
  position: { x: number; y: number };
  error?: string;
}

export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  label?: string;
  animated?: boolean;
}

export interface WorkflowDraft {
  id: string;
  name: string;
  description: string;
  status: WorkflowStatus;
  nodes: FlowNode[];
  edges: FlowEdge[];
  assumptions: string[];
  unresolvedFields: string[];
  createdAt: string;
  updatedAt: string;
}

// ─── Validation ──────────────────────────────────────────────────────────────

export type ValidationSeverity = "error" | "warning" | "info";

export interface ValidationIssue {
  id: string;
  nodeId?: string;
  severity: ValidationSeverity;
  message: string;
  suggestion?: string;
}

export interface ValidationResult {
  valid: boolean;
  issues: ValidationIssue[];
}

// ─── Chat ────────────────────────────────────────────────────────────────────

export type ChatMessageKind =
  | "user"
  | "assistant_text"
  | "workflow_proposal"
  | "validation_summary"
  | "execution_event"
  | "approval_request"
  | "system_notice";

export interface StudioChatMessage {
  id: string;
  kind: ChatMessageKind;
  text: string;
  timestamp: string;
  workflowSummary?: string;
  assumptions?: string[];
  unresolvedFields?: string[];
  validationResult?: ValidationResult;
  executionEvent?: ExecutionEvent;
}

// ─── Execution ───────────────────────────────────────────────────────────────

export type ExecutionEventType =
  | "started"
  | "node_started"
  | "node_completed"
  | "node_failed"
  | "waiting_for_approval"
  | "approval_granted"
  | "completed"
  | "failed";

export interface ExecutionEvent {
  id: string;
  type: ExecutionEventType;
  nodeId?: string;
  nodeName?: string;
  message: string;
  timestamp: string;
}

export type ExecutionStatus = "idle" | "running" | "paused" | "completed" | "failed";

// ─── Patch ───────────────────────────────────────────────────────────────────

export type PatchOperation =
  | { type: "add_node"; node: FlowNode; edges: FlowEdge[] }
  | { type: "remove_node"; nodeId: string }
  | { type: "update_node"; nodeId: string; changes: Partial<FlowNode> }
  | { type: "replace_provider"; nodeId: string; provider: string; tool: string }
  | { type: "update_schedule"; nodeId: string; schedule: string }
  | { type: "add_edge"; edge: FlowEdge }
  | { type: "remove_edge"; edgeId: string };

export interface WorkflowPatchResult {
  success: boolean;
  operations: PatchOperation[];
  description: string;
}
