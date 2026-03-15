// ─── Agent catalog ───────────────────────────────────────────────────────────

export type AgentCategory =
  | "Data & Analytics"
  | "Finance"
  | "Productivity"
  | "Developer Tools"
  | "Research"
  | "Communication"
  | "Security";

export type AgentCapability =
  | "Web Search"
  | "Code Execution"
  | "File I/O"
  | "API Calls"
  | "Data Analysis"
  | "Payment"
  | "Email"
  | "Scheduling";

export type AgentStatus = "idle" | "running" | "success" | "error" | "paused";

export type AgentPublisher = "Tesseris" | "Community";

export interface AgentBadges {
  verified: boolean;
  txEnabled: boolean;
  tokenListed: boolean;
}

export type AgentIconName =
  | "FlaskConical"
  | "Code2"
  | "CreditCard"
  | "BarChart3"
  | "Shield"
  | "TrendingUp"
  | "Mail"
  | "CalendarDays"
  | "Globe"
  | "Megaphone";

export interface Agent {
  id: string;
  name: string;
  description: string;
  longDescription: string;
  category: AgentCategory;
  capabilities: AgentCapability[];
  author: string;
  publisher: AgentPublisher;
  version: string;
  rating: number;
  reviewCount: number;
  runCount: number;
  iconName: AgentIconName;
  accentColor: string;
  tags: string[];
  badges: AgentBadges;
  inputSchema: AgentInputField[];
}

export interface AgentInputField {
  key: string;
  label: string;
  type: "text" | "textarea" | "number" | "select" | "boolean";
  placeholder?: string;
  options?: string[];
  required: boolean;
  defaultValue?: string;
}

export interface InstalledAgent {
  agentId: string;
  installedAt: string;
  pinnedToSidebar: boolean;
}

// ─── Runs ─────────────────────────────────────────────────────────────────────

export type RunStatus = "queued" | "running" | "success" | "error" | "aborted";

export interface RunStep {
  id: string;
  label: string;
  status: "pending" | "running" | "done" | "error";
  output?: string;
  startedAt?: string;
  finishedAt?: string;
}

export interface AgentRun {
  id: string;
  agentId: string;
  agentName: string;
  agentIconName: AgentIconName;
  status: RunStatus;
  inputs: Record<string, string>;
  steps: RunStep[];
  output: string;
  startedAt: string;
  finishedAt?: string;
  durationMs?: number;
  tokenCount?: number;
}

// ─── Chat ─────────────────────────────────────────────────────────────────────

export type ChatRole = "user" | "agent" | "system";

export interface ChatMessage {
  id: string;
  role: ChatRole;
  text: string;
  timestamp: string;
  runId?: string;
}

export type ConversationMessageType = "text" | "run-card" | "run-complete";

export interface ConversationMessage {
  id: string;
  role: ChatRole;
  text: string;
  timestamp: string;
  type: ConversationMessageType;
  runId?: string;
  run?: AgentRun;
}

export interface Conversation {
  id: string;
  title: string;
  agentId: string;
  messages: ConversationMessage[];
  createdAt: string;
  updatedAt: string;
}

// ─── Navigation ───────────────────────────────────────────────────────────────

export type AppView =
  | "chat"
  | "news"
  | "explorer"
  | "store"
  | "tasks"
  | "integrations"
  | "wallet"
  | "history"
  | "memory"
  | "inbox"
  | "settings"
  | "studio"
  | "portfolio";

export type WorkspaceTab = "chat" | "run" | "monitor" | "history";

export type ActivityBarItem =
  | { type: "store" }
  | { type: "agent"; agentId: string };

// ─── Tasks ────────────────────────────────────────────────────────────────────

export type TaskStatus = "running" | "waiting" | "scheduled" | "completed" | "failed";

export interface TaskItem {
  id: string;
  title: string;
  intentSummary: string;
  status: TaskStatus;
  agentId: string;
  agentName: string;
  agentIconName: AgentIconName;
  progress: number;
  category: string;
  integrations: string[];
  costEstimate?: string;
  approvalRequired: boolean;
  lastUpdated: string;
  createdAt: string;
  scheduledFor?: string;
}

// ─── Integrations ─────────────────────────────────────────────────────────────

export type IntegrationType =
  | "channel"
  | "productivity"
  | "knowledge"
  | "commerce"
  | "web3"
  | "mcp"
  | "browser"
  | "custom";

export type IntegrationStatus = "connected" | "disconnected" | "error" | "pending";

export interface Integration {
  id: string;
  name: string;
  type: IntegrationType;
  description: string;
  icon: string;
  status: IntegrationStatus;
  riskLevel: "low" | "medium" | "high";
  lastSync?: string;
  connectedAgents: number;
  scopes: string[];
}

// ─── Wallet / Approvals ──────────────────────────────────────────────────────

export type ApprovalStatus = "pending" | "approved" | "rejected" | "expired";
export type RiskLevel = "low" | "medium" | "high" | "critical";

export interface ApprovalItem {
  id: string;
  taskName: string;
  agentName: string;
  agentIconName: AgentIconName;
  requestedAction: string;
  amount?: string;
  riskLevel: RiskLevel;
  expiresAt: string;
  status: ApprovalStatus;
  createdAt: string;
}

export interface WalletInfo {
  id: string;
  name: string;
  address: string;
  network: string;
  balance: string;
  isDefault: boolean;
  status: "connected" | "disconnected";
}

export interface ReceiptItem {
  id: string;
  taskName: string;
  agentName: string;
  amount: string;
  status: "settled" | "pending" | "refunded";
  date: string;
  txHash?: string;
}

// ─── History ──────────────────────────────────────────────────────────────────

export interface HistoryItem {
  id: string;
  title: string;
  date: string;
  status: "success" | "error" | "aborted";
  agentNames: string[];
  integrations: string[];
  artifactCount: number;
  hasReceipt: boolean;
  durationMs: number;
  type: "run" | "artifact" | "conversation" | "receipt" | "flow";
}

// ─── Memory ───────────────────────────────────────────────────────────────────

export interface MemoryEntity {
  id: string;
  name: string;
  type: "preference" | "knowledge" | "entity" | "source" | "privacy";
  description: string;
  lastUpdated: string;
  category: string;
}

// ─── Inbox ────────────────────────────────────────────────────────────────────

export type InboxSeverity = "info" | "warning" | "error" | "success" | "action";
export type InboxCategory = "action_required" | "update" | "completion" | "alert" | "suggestion";

export interface InboxItem {
  id: string;
  title: string;
  description: string;
  severity: InboxSeverity;
  category: InboxCategory;
  timestamp: string;
  relatedTaskId?: string;
  relatedIntegrationId?: string;
  isRead: boolean;
  primaryAction?: string;
}
