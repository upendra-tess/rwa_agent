import type {
  TaskItem,
  Integration,
  ApprovalItem,
  WalletInfo,
  ReceiptItem,
  HistoryItem,
  MemoryEntity,
  InboxItem,
} from "../types";

// ─── Tasks ────────────────────────────────────────────────────────────────────

export const MOCK_TASKS: TaskItem[] = [
  {
    id: "task-001",
    title: "Research DeFi yield strategies Q1 2026",
    intentSummary: "Find and compare top DeFi yield strategies with risk analysis",
    status: "running",
    agentId: "research-analyst",
    agentName: "Research Analyst",
    agentIconName: "FlaskConical",
    progress: 65,
    category: "Research",
    integrations: ["Web Search", "Data Analysis"],
    costEstimate: "$0.12",
    approvalRequired: false,
    lastUpdated: "2026-03-10T23:30:00Z",
    createdAt: "2026-03-10T23:15:00Z",
  },
  {
    id: "task-002",
    title: "Audit Escrow.sol smart contract",
    intentSummary: "Full security audit of the updated escrow contract",
    status: "waiting",
    agentId: "security-auditor",
    agentName: "Security Auditor",
    agentIconName: "Shield",
    progress: 0,
    category: "Security",
    integrations: ["Code Execution", "Web Search"],
    costEstimate: "$0.45",
    approvalRequired: true,
    lastUpdated: "2026-03-10T22:45:00Z",
    createdAt: "2026-03-10T22:40:00Z",
  },
  {
    id: "task-003",
    title: "Weekly invoice reconciliation",
    intentSummary: "Reconcile all USDC invoices from the past 7 days",
    status: "scheduled",
    agentId: "payment-ops",
    agentName: "Payment Ops Agent",
    agentIconName: "CreditCard",
    progress: 0,
    category: "Finance",
    integrations: ["Payment", "API Calls"],
    costEstimate: "$0.08",
    approvalRequired: false,
    lastUpdated: "2026-03-10T20:00:00Z",
    createdAt: "2026-03-10T18:00:00Z",
    scheduledFor: "2026-03-11T09:00:00Z",
  },
  {
    id: "task-004",
    title: "Analyse monthly sales data trends",
    intentSummary: "Identify seasonality and anomalies in 36-month sales data",
    status: "completed",
    agentId: "data-analyst",
    agentName: "Data Analyst",
    agentIconName: "BarChart3",
    progress: 100,
    category: "Data & Analytics",
    integrations: ["Data Analysis", "File I/O"],
    costEstimate: "$0.15",
    approvalRequired: false,
    lastUpdated: "2026-03-10T19:30:00Z",
    createdAt: "2026-03-10T19:10:00Z",
  },
  {
    id: "task-005",
    title: "Portfolio rebalancing recommendation",
    intentSummary: "Track portfolio and suggest rebalancing actions",
    status: "completed",
    agentId: "portfolio-tracker",
    agentName: "Portfolio Tracker",
    agentIconName: "TrendingUp",
    progress: 100,
    category: "Finance",
    integrations: ["API Calls", "Data Analysis"],
    costEstimate: "$0.20",
    approvalRequired: false,
    lastUpdated: "2026-03-10T18:00:00Z",
    createdAt: "2026-03-10T17:45:00Z",
  },
  {
    id: "task-006",
    title: "Review PR #142 security patterns",
    intentSummary: "Automated code review for security and performance",
    status: "failed",
    agentId: "code-reviewer",
    agentName: "Code Reviewer",
    agentIconName: "Code2",
    progress: 42,
    category: "Developer Tools",
    integrations: ["Code Execution", "API Calls"],
    costEstimate: "$0.10",
    approvalRequired: false,
    lastUpdated: "2026-03-10T16:20:00Z",
    createdAt: "2026-03-10T16:00:00Z",
  },
  {
    id: "task-007",
    title: "Draft follow-up email for partnership",
    intentSummary: "Compose professional follow-up after demo meeting",
    status: "running",
    agentId: "email-composer",
    agentName: "Email Composer",
    agentIconName: "Mail",
    progress: 80,
    category: "Communication",
    integrations: ["Email"],
    approvalRequired: false,
    lastUpdated: "2026-03-10T23:45:00Z",
    createdAt: "2026-03-10T23:40:00Z",
  },
  {
    id: "task-008",
    title: "Schedule team sync for next week",
    intentSummary: "Find optimal time for 5-person team meeting",
    status: "waiting",
    agentId: "scheduler",
    agentName: "Meeting Scheduler",
    agentIconName: "CalendarDays",
    progress: 30,
    category: "Productivity",
    integrations: ["Scheduling", "Email"],
    approvalRequired: true,
    lastUpdated: "2026-03-10T23:20:00Z",
    createdAt: "2026-03-10T23:10:00Z",
  },
];

// ─── Integrations ─────────────────────────────────────────────────────────────

export const MOCK_INTEGRATIONS: Integration[] = [
  // Channels
  { id: "int-telegram", name: "Telegram", type: "channel", description: "Send and receive messages via Telegram bots", icon: "MessageCircle", status: "connected", riskLevel: "low", lastSync: "2026-03-10T23:50:00Z", connectedAgents: 3, scopes: ["read", "write"] },
  { id: "int-discord", name: "Discord", type: "channel", description: "Integrate with Discord servers and channels", icon: "Hash", status: "connected", riskLevel: "low", lastSync: "2026-03-10T23:48:00Z", connectedAgents: 2, scopes: ["read", "write"] },
  { id: "int-twitter", name: "X / Twitter", type: "channel", description: "Post tweets, read timeline, manage DMs", icon: "AtSign", status: "disconnected", riskLevel: "medium", connectedAgents: 0, scopes: [] },
  { id: "int-slack", name: "Slack", type: "channel", description: "Send notifications and respond in Slack channels", icon: "Hash", status: "connected", riskLevel: "low", lastSync: "2026-03-10T23:30:00Z", connectedAgents: 4, scopes: ["read", "write"] },
  { id: "int-whatsapp", name: "WhatsApp", type: "channel", description: "Business messaging via WhatsApp API", icon: "Phone", status: "disconnected", riskLevel: "medium", connectedAgents: 0, scopes: [] },
  { id: "int-gmail", name: "Gmail", type: "channel", description: "Read, compose, and send emails via Gmail", icon: "Mail", status: "connected", riskLevel: "medium", lastSync: "2026-03-10T23:45:00Z", connectedAgents: 2, scopes: ["read", "write", "send"] },

  // Productivity
  { id: "int-gcal", name: "Google Calendar", type: "productivity", description: "Manage events, check availability, schedule meetings", icon: "Calendar", status: "connected", riskLevel: "low", lastSync: "2026-03-10T23:00:00Z", connectedAgents: 1, scopes: ["read", "write"] },
  { id: "int-gdrive", name: "Google Drive", type: "knowledge", description: "Access and manage files in Google Drive", icon: "HardDrive", status: "connected", riskLevel: "medium", lastSync: "2026-03-10T22:30:00Z", connectedAgents: 2, scopes: ["read", "write"] },
  { id: "int-notion", name: "Notion", type: "knowledge", description: "Read and write to Notion databases and pages", icon: "FileText", status: "connected", riskLevel: "low", lastSync: "2026-03-10T22:00:00Z", connectedAgents: 1, scopes: ["read", "write"] },
  { id: "int-github", name: "GitHub", type: "productivity", description: "Access repos, PRs, issues, and actions", icon: "GitBranch", status: "connected", riskLevel: "high", lastSync: "2026-03-10T23:55:00Z", connectedAgents: 3, scopes: ["read", "write", "execute"] },

  // Web3
  { id: "int-wallet-connect", name: "Wallet Connector", type: "web3", description: "Connect crypto wallets for transactions", icon: "Wallet", status: "connected", riskLevel: "high", lastSync: "2026-03-10T23:50:00Z", connectedAgents: 2, scopes: ["read", "sign", "transact"] },

  // MCP
  { id: "int-browser", name: "Browser Operator", type: "browser", description: "Autonomous web browsing and scraping", icon: "Globe", status: "connected", riskLevel: "medium", lastSync: "2026-03-10T23:40:00Z", connectedAgents: 4, scopes: ["browse", "screenshot", "interact"] },
  { id: "int-mcp-custom", name: "Custom MCP Server", type: "mcp", description: "Connect to your own MCP server endpoint", icon: "Server", status: "disconnected", riskLevel: "high", connectedAgents: 0, scopes: [] },
  { id: "int-webhook", name: "Webhook Endpoint", type: "custom", description: "Receive and send webhook events", icon: "Zap", status: "connected", riskLevel: "low", lastSync: "2026-03-10T23:30:00Z", connectedAgents: 1, scopes: ["receive", "send"] },
];

// ─── Approvals ────────────────────────────────────────────────────────────────

export const MOCK_APPROVALS: ApprovalItem[] = [
  {
    id: "appr-001",
    taskName: "Send partnership follow-up email",
    agentName: "Email Composer",
    agentIconName: "Mail",
    requestedAction: "Send email via connected Gmail account",
    riskLevel: "low",
    expiresAt: "2026-03-11T06:00:00Z",
    status: "pending",
    createdAt: "2026-03-10T23:40:00Z",
  },
  {
    id: "appr-002",
    taskName: "Execute portfolio rebalance",
    agentName: "Portfolio Tracker",
    agentIconName: "TrendingUp",
    requestedAction: "Sign transaction to swap 2,000 USDC → ETH",
    amount: "$2,000.00",
    riskLevel: "high",
    expiresAt: "2026-03-11T03:00:00Z",
    status: "pending",
    createdAt: "2026-03-10T23:30:00Z",
  },
  {
    id: "appr-003",
    taskName: "Audit Escrow.sol contract",
    agentName: "Security Auditor",
    agentIconName: "Shield",
    requestedAction: "Access GitHub repo and execute analysis tools",
    riskLevel: "medium",
    expiresAt: "2026-03-11T12:00:00Z",
    status: "pending",
    createdAt: "2026-03-10T22:45:00Z",
  },
  {
    id: "appr-004",
    taskName: "Weekly payment reconciliation",
    agentName: "Payment Ops Agent",
    agentIconName: "CreditCard",
    requestedAction: "Access payment rails for invoice matching",
    amount: "$0.08",
    riskLevel: "low",
    expiresAt: "2026-03-11T09:00:00Z",
    status: "pending",
    createdAt: "2026-03-10T20:00:00Z",
  },
  {
    id: "appr-005",
    taskName: "Book flight to SF",
    agentName: "Research Analyst",
    agentIconName: "FlaskConical",
    requestedAction: "Purchase airline ticket via connected payment method",
    amount: "$489.00",
    riskLevel: "critical",
    expiresAt: "2026-03-10T22:00:00Z",
    status: "expired",
    createdAt: "2026-03-10T16:00:00Z",
  },
];

// ─── Wallets ──────────────────────────────────────────────────────────────────

export const MOCK_WALLETS: WalletInfo[] = [
  { id: "w-001", name: "Main Wallet", address: "0x7A3c...91F2", network: "Ethereum", balance: "$12,450.00", isDefault: true, status: "connected" },
  { id: "w-002", name: "Agent Escrow", address: "0x3B2e...A4D8", network: "Base", balance: "$2,180.00", isDefault: false, status: "connected" },
  { id: "w-003", name: "Solana Wallet", address: "9kHv...mR7x", network: "Solana", balance: "$890.50", isDefault: false, status: "disconnected" },
];

// ─── Receipts ─────────────────────────────────────────────────────────────────

export const MOCK_RECEIPTS: ReceiptItem[] = [
  { id: "rcpt-001", taskName: "DeFi yield research report", agentName: "Research Analyst", amount: "$0.12", status: "settled", date: "2026-03-10T19:30:00Z", txHash: "0xabc123..." },
  { id: "rcpt-002", taskName: "Portfolio analysis", agentName: "Portfolio Tracker", amount: "$0.20", status: "settled", date: "2026-03-10T18:00:00Z", txHash: "0xdef456..." },
  { id: "rcpt-003", taskName: "Code review PR #139", agentName: "Code Reviewer", amount: "$0.10", status: "settled", date: "2026-03-09T14:20:00Z", txHash: "0xghi789..." },
  { id: "rcpt-004", taskName: "Sales data analysis", agentName: "Data Analyst", amount: "$0.15", status: "pending", date: "2026-03-10T19:30:00Z" },
  { id: "rcpt-005", taskName: "SEO audit for landing page", agentName: "SEO Optimizer", amount: "$0.05", status: "refunded", date: "2026-03-08T10:00:00Z", txHash: "0xjkl012..." },
];

// ─── History ──────────────────────────────────────────────────────────────────

export const MOCK_HISTORY: HistoryItem[] = [
  { id: "hist-001", title: "DeFi yield strategies research", date: "2026-03-10T19:30:00Z", status: "success", agentNames: ["Research Analyst"], integrations: ["Web Search", "Data Analysis"], artifactCount: 2, hasReceipt: true, durationMs: 45000, type: "run" },
  { id: "hist-002", title: "Portfolio rebalancing analysis", date: "2026-03-10T18:00:00Z", status: "success", agentNames: ["Portfolio Tracker"], integrations: ["API Calls"], artifactCount: 1, hasReceipt: true, durationMs: 32000, type: "run" },
  { id: "hist-003", title: "PR #139 security review", date: "2026-03-09T14:20:00Z", status: "success", agentNames: ["Code Reviewer"], integrations: ["GitHub", "Code Execution"], artifactCount: 1, hasReceipt: true, durationMs: 67000, type: "run" },
  { id: "hist-004", title: "Invoice reconciliation — Week 9", date: "2026-03-08T09:00:00Z", status: "success", agentNames: ["Payment Ops Agent"], integrations: ["Payment", "API Calls"], artifactCount: 3, hasReceipt: true, durationMs: 120000, type: "run" },
  { id: "hist-005", title: "SEO audit — landing page", date: "2026-03-08T10:00:00Z", status: "error", agentNames: ["SEO Optimizer"], integrations: ["Web Search"], artifactCount: 0, hasReceipt: true, durationMs: 15000, type: "run" },
  { id: "hist-006", title: "Team meeting scheduling", date: "2026-03-07T16:30:00Z", status: "success", agentNames: ["Meeting Scheduler"], integrations: ["Google Calendar", "Email"], artifactCount: 0, hasReceipt: false, durationMs: 8000, type: "run" },
  { id: "hist-007", title: "Q4 2025 Sales Report.pdf", date: "2026-03-06T12:00:00Z", status: "success", agentNames: ["Data Analyst"], integrations: ["File I/O"], artifactCount: 1, hasReceipt: false, durationMs: 0, type: "artifact" },
  { id: "hist-008", title: "Competitor analysis conversation", date: "2026-03-05T09:15:00Z", status: "success", agentNames: ["Research Analyst"], integrations: ["Web Search"], artifactCount: 0, hasReceipt: false, durationMs: 0, type: "conversation" },
  { id: "hist-009", title: "Escrow.sol audit — v1 flow", date: "2026-03-04T11:00:00Z", status: "aborted", agentNames: ["Security Auditor"], integrations: ["GitHub"], artifactCount: 0, hasReceipt: false, durationMs: 25000, type: "flow" },
  { id: "hist-010", title: "Social media campaign posts", date: "2026-03-03T15:00:00Z", status: "success", agentNames: ["Social Media Writer"], integrations: ["Web Search"], artifactCount: 4, hasReceipt: false, durationMs: 22000, type: "run" },
];

// ─── Memory ───────────────────────────────────────────────────────────────────

export const MOCK_MEMORY: MemoryEntity[] = [
  // Preferences
  { id: "mem-001", name: "Budget limit per task", type: "preference", description: "Max $5.00 per agent run without additional approval", lastUpdated: "2026-03-09T12:00:00Z", category: "Budget" },
  { id: "mem-002", name: "Notification channel", type: "preference", description: "Send task updates via Telegram, urgent alerts via Email", lastUpdated: "2026-03-08T10:00:00Z", category: "Notifications" },
  { id: "mem-003", name: "Default output format", type: "preference", description: "Prefer Markdown for reports, JSON for data exports", lastUpdated: "2026-03-07T15:00:00Z", category: "Output" },
  { id: "mem-004", name: "Preferred agent style", type: "preference", description: "Concise, data-driven responses with citations", lastUpdated: "2026-03-06T09:00:00Z", category: "Behavior" },

  // Knowledge
  { id: "mem-005", name: "DeFi protocols reference", type: "knowledge", description: "Curated list of top DeFi protocols with risk scores", lastUpdated: "2026-03-10T18:00:00Z", category: "Files" },
  { id: "mem-006", name: "Company brand guidelines", type: "knowledge", description: "Uploaded PDF with logo usage, tone, and color specs", lastUpdated: "2026-03-05T14:00:00Z", category: "Files" },
  { id: "mem-007", name: "Product roadmap notes", type: "knowledge", description: "Q1–Q2 2026 product priorities and milestones", lastUpdated: "2026-03-04T11:00:00Z", category: "Notes" },

  // Saved entities
  { id: "mem-008", name: "Main ETH wallet", type: "entity", description: "0x7A3c...91F2 — Primary wallet for transactions", lastUpdated: "2026-03-10T23:00:00Z", category: "Wallets" },
  { id: "mem-009", name: "Aave Protocol", type: "entity", description: "Favourite DeFi protocol for yield strategies", lastUpdated: "2026-03-09T16:00:00Z", category: "Protocols" },
  { id: "mem-010", name: "Research Analyst", type: "entity", description: "Pinned as default agent for research tasks", lastUpdated: "2026-03-10T20:00:00Z", category: "Agents" },

  // Trusted sources
  { id: "mem-011", name: "CoinGecko API", type: "source", description: "Approved data source for crypto pricing", lastUpdated: "2026-03-08T09:00:00Z", category: "APIs" },
  { id: "mem-012", name: "DefiLlama", type: "source", description: "Approved source for TVL and protocol metrics", lastUpdated: "2026-03-07T12:00:00Z", category: "APIs" },

  // Privacy
  { id: "mem-013", name: "Conversation retention", type: "privacy", description: "Keep conversation history for 90 days, then auto-delete", lastUpdated: "2026-03-01T10:00:00Z", category: "Retention" },
  { id: "mem-014", name: "No PII in agent logs", type: "privacy", description: "Redact personal information from all agent run logs", lastUpdated: "2026-03-01T10:00:00Z", category: "Redaction" },
];

// ─── Inbox ────────────────────────────────────────────────────────────────────

export const MOCK_INBOX: InboxItem[] = [
  {
    id: "inbox-001",
    title: "Approval required: Send partnership email",
    description: "Email Composer wants to send an email via your connected Gmail account.",
    severity: "action",
    category: "action_required",
    timestamp: "2026-03-10T23:40:00Z",
    relatedTaskId: "task-007",
    isRead: false,
    primaryAction: "Review & Approve",
  },
  {
    id: "inbox-002",
    title: "Approval required: Portfolio rebalance transaction",
    description: "Portfolio Tracker wants to sign a transaction to swap 2,000 USDC → ETH.",
    severity: "warning",
    category: "action_required",
    timestamp: "2026-03-10T23:30:00Z",
    relatedTaskId: "task-005",
    isRead: false,
    primaryAction: "Review & Approve",
  },
  {
    id: "inbox-003",
    title: "Task completed: Sales data analysis",
    description: "Data Analyst finished analysing your 36-month sales data. 2 artifacts generated.",
    severity: "success",
    category: "completion",
    timestamp: "2026-03-10T19:30:00Z",
    relatedTaskId: "task-004",
    isRead: false,
    primaryAction: "View Results",
  },
  {
    id: "inbox-004",
    title: "Task failed: PR #142 review",
    description: "Code Reviewer encountered an error at step 3 of 6. The target branch was force-pushed during analysis.",
    severity: "error",
    category: "alert",
    timestamp: "2026-03-10T16:20:00Z",
    relatedTaskId: "task-006",
    isRead: true,
    primaryAction: "Retry Task",
  },
  {
    id: "inbox-005",
    title: "X / Twitter integration disconnected",
    description: "Your X / Twitter token has expired. Reconnect to allow agents to post on your behalf.",
    severity: "warning",
    category: "alert",
    timestamp: "2026-03-10T15:00:00Z",
    relatedIntegrationId: "int-twitter",
    isRead: true,
    primaryAction: "Reconnect",
  },
  {
    id: "inbox-006",
    title: "Scheduled task reminder: Invoice reconciliation",
    description: "Weekly invoice reconciliation is scheduled to run tomorrow at 09:00 UTC.",
    severity: "info",
    category: "update",
    timestamp: "2026-03-10T20:00:00Z",
    relatedTaskId: "task-003",
    isRead: true,
  },
  {
    id: "inbox-007",
    title: "Suggested: Try the Security Auditor",
    description: "Based on your recent GitHub activity, you might benefit from automated smart contract audits.",
    severity: "info",
    category: "suggestion",
    timestamp: "2026-03-10T14:00:00Z",
    isRead: true,
  },
  {
    id: "inbox-008",
    title: "Task completed: Portfolio rebalancing",
    description: "Portfolio Tracker completed the analysis. Current allocation is within strategy bounds.",
    severity: "success",
    category: "completion",
    timestamp: "2026-03-10T18:00:00Z",
    relatedTaskId: "task-005",
    isRead: true,
    primaryAction: "View Report",
  },
];

// ─── Badge counts (derived) ──────────────────────────────────────────────────

export function getBadgeCounts() {
  const activeTasks = MOCK_TASKS.filter((t) => t.status === "running" || t.status === "waiting").length;
  const pendingApprovals = MOCK_APPROVALS.filter((a) => a.status === "pending").length;
  const unreadInbox = MOCK_INBOX.filter((i) => !i.isRead).length;

  return {
    tasks: activeTasks,
    wallet: pendingApprovals,
    inbox: unreadInbox,
  };
}
