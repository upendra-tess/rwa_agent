/**
 * TessFlow Studio — Mock Orchestrator.
 * Typed mock functions that simulate backend workflow orchestration.
 * Replace these with real API calls when backend is ready.
 */

import type {
  WorkflowDraft,
  FlowNode,
  FlowEdge,
  ValidationResult,
  WorkflowPatchResult,
  ExecutionEvent,
} from "./types";

// ─── Helpers ─────────────────────────────────────────────────────────────────

const uid = () => `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
const now = () => new Date().toISOString();

const delay = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

// ─── Workflow Scenario Templates ─────────────────────────────────────────────

interface ScenarioTemplate {
  keywords: string[];
  name: string;
  description: string;
  assumptions: string[];
  unresolvedFields: string[];
  nodes: FlowNode[];
  edges: FlowEdge[];
}

const SCENARIOS: ScenarioTemplate[] = [
  {
    keywords: ["wallet", "monitor", "alert", "telegram", "meme", "solana"],
    name: "Wallet Monitor & Alert Pipeline",
    description: "Monitors top wallets for new Solana meme coin purchases and sends alerts when multiple tracked wallets buy the same token.",
    assumptions: [
      "Tracking top 50 wallets by volume",
      "Alert threshold set to 3 wallets buying same token",
      "Using Helius RPC for Solana data",
      "Telegram bot token configured",
    ],
    unresolvedFields: ["Telegram bot token", "Target chat ID"],
    nodes: [
      { id: "n1", kind: "trigger", title: "Wallet Watcher", description: "Monitor tracked wallets every 30s", status: "idle", config: { provider: "Helius", tool: "wallet_monitor", schedule: "*/30 * * * * *", authStatus: "connected" }, position: { x: 0, y: 0 } },
      { id: "n2", kind: "tool", title: "Token Resolver", description: "Resolve token metadata and market data", status: "idle", config: { provider: "Jupiter", tool: "token_lookup", retryCount: 2, timeout: 10, authStatus: "connected" }, position: { x: 0, y: 150 } },
      { id: "n3", kind: "agent", title: "Pattern Analyzer", description: "Detect multi-wallet convergence patterns", status: "idle", config: { provider: "TessFlow", tool: "convergence_detector", inputs: { threshold: "3" }, authStatus: "not_required" }, position: { x: 0, y: 300 } },
      { id: "n4", kind: "condition", title: "Alert Threshold", description: "Check if ≥3 wallets bought same token", status: "idle", config: { conditionExpression: "convergence_count >= 3", conditionTrueBranch: "n5", conditionFalseBranch: "n6" }, position: { x: 0, y: 450 } },
      { id: "n5", kind: "transform", title: "Format Alert", description: "Build Telegram message with token info", status: "idle", config: { provider: "TessFlow", tool: "message_formatter", authStatus: "not_required" }, position: { x: -150, y: 600 } },
      { id: "n6", kind: "output", title: "Log Only", description: "Store event for later analysis", status: "idle", config: { provider: "TessFlow", tool: "event_logger", authStatus: "not_required" }, position: { x: 150, y: 600 } },
      { id: "n7", kind: "output", title: "Send Telegram", description: "Push alert to Telegram channel", status: "idle", config: { provider: "Telegram", tool: "send_message", authStatus: "disconnected" }, position: { x: -150, y: 750 } },
    ],
    edges: [
      { id: "e1", source: "n1", target: "n2" },
      { id: "e2", source: "n2", target: "n3" },
      { id: "e3", source: "n3", target: "n4" },
      { id: "e4", source: "n4", target: "n5", label: "Yes" },
      { id: "e5", source: "n4", target: "n6", label: "No" },
      { id: "e6", source: "n5", target: "n7" },
    ],
  },
  {
    keywords: ["governance", "proposal", "discord", "summarize", "hour"],
    name: "Governance Proposal Monitor",
    description: "Summarizes new governance proposals every hour and sends high-priority ones to Discord.",
    assumptions: [
      "Monitoring Snapshot and Tally for proposals",
      "Using GPT-4 for summarization",
      "Priority defined by vote weight and deadline proximity",
    ],
    unresolvedFields: ["Discord webhook URL"],
    nodes: [
      { id: "n1", kind: "trigger", title: "Proposal Scanner", description: "Check for new proposals every hour", status: "idle", config: { provider: "Snapshot", tool: "proposal_feed", schedule: "0 * * * *", authStatus: "connected" }, position: { x: 0, y: 0 } },
      { id: "n2", kind: "agent", title: "Summarizer Agent", description: "Summarize proposal content and implications", status: "idle", config: { provider: "OpenAI", tool: "gpt-4-summarizer", retryCount: 1, timeout: 30, authStatus: "connected" }, position: { x: 0, y: 150 } },
      { id: "n3", kind: "condition", title: "Priority Check", description: "Filter high-priority proposals", status: "idle", config: { conditionExpression: "priority === 'high'", conditionTrueBranch: "n4", conditionFalseBranch: "n5" }, position: { x: 0, y: 300 } },
      { id: "n4", kind: "approval", title: "Review Gate", description: "Require human review before posting", status: "idle", config: { approvalRequired: true }, position: { x: -150, y: 450 } },
      { id: "n5", kind: "output", title: "Archive", description: "Store summary for reference", status: "idle", config: { provider: "TessFlow", tool: "storage", authStatus: "not_required" }, position: { x: 150, y: 450 } },
      { id: "n6", kind: "output", title: "Post to Discord", description: "Send summary to Discord channel", status: "idle", config: { provider: "Discord", tool: "webhook_post", authStatus: "disconnected" }, position: { x: -150, y: 600 } },
    ],
    edges: [
      { id: "e1", source: "n1", target: "n2" },
      { id: "e2", source: "n2", target: "n3" },
      { id: "e3", source: "n3", target: "n4", label: "High" },
      { id: "e4", source: "n3", target: "n5", label: "Low" },
      { id: "e5", source: "n4", target: "n6" },
    ],
  },
  {
    keywords: ["smart money", "swap", "unusual", "activity", "task", "follow"],
    name: "Smart Money Activity Tracker",
    description: "Watches smart money swap activity and creates follow-up tasks when unusual patterns are detected.",
    assumptions: [
      "Tracking top 100 DeFi wallets",
      "Unusual activity: swaps > $50k or new token positions",
      "Follow-up tasks created in TessFlow task queue",
    ],
    unresolvedFields: [],
    nodes: [
      { id: "n1", kind: "trigger", title: "DEX Listener", description: "Stream swap events from major DEXes", status: "idle", config: { provider: "Dune", tool: "dex_swap_feed", schedule: "continuous", authStatus: "connected" }, position: { x: 0, y: 0 } },
      { id: "n2", kind: "tool", title: "Wallet Enricher", description: "Classify wallet and get historical context", status: "idle", config: { provider: "Arkham", tool: "wallet_lookup", retryCount: 2, timeout: 15, authStatus: "connected" }, position: { x: 0, y: 150 } },
      { id: "n3", kind: "agent", title: "Anomaly Detector", description: "Score activity for unusualness", status: "idle", config: { provider: "TessFlow", tool: "anomaly_scorer", authStatus: "not_required" }, position: { x: 0, y: 300 } },
      { id: "n4", kind: "condition", title: "Threshold Gate", description: "Only proceed if anomaly score > 0.7", status: "idle", config: { conditionExpression: "anomaly_score > 0.7", conditionTrueBranch: "n5", conditionFalseBranch: "n6" }, position: { x: 0, y: 450 } },
      { id: "n5", kind: "transform", title: "Build Task", description: "Generate structured follow-up task", status: "idle", config: { provider: "TessFlow", tool: "task_builder", authStatus: "not_required" }, position: { x: -150, y: 600 } },
      { id: "n6", kind: "output", title: "Skip", description: "Log and skip normal activity", status: "idle", config: { provider: "TessFlow", tool: "event_logger", authStatus: "not_required" }, position: { x: 150, y: 600 } },
      { id: "n7", kind: "output", title: "Create Task", description: "Add task to TessFlow queue", status: "idle", config: { provider: "TessFlow", tool: "task_queue", authStatus: "connected" }, position: { x: -150, y: 750 } },
    ],
    edges: [
      { id: "e1", source: "n1", target: "n2" },
      { id: "e2", source: "n2", target: "n3" },
      { id: "e3", source: "n3", target: "n4" },
      { id: "e4", source: "n4", target: "n5", label: "Unusual" },
      { id: "e5", source: "n4", target: "n6", label: "Normal" },
      { id: "e6", source: "n5", target: "n7" },
    ],
  },
];

// Default fallback scenario
const DEFAULT_SCENARIO: ScenarioTemplate = {
  keywords: [],
  name: "Custom Automation Workflow",
  description: "A custom workflow generated from your request.",
  assumptions: ["Using default configuration", "All integrations assumed available"],
  unresolvedFields: [],
  nodes: [
    { id: "n1", kind: "trigger", title: "Trigger", description: "Start the workflow on schedule", status: "idle", config: { provider: "TessFlow", tool: "scheduler", schedule: "0 * * * *", authStatus: "not_required" }, position: { x: 0, y: 0 } },
    { id: "n2", kind: "tool", title: "Fetch Data", description: "Retrieve data from source", status: "idle", config: { provider: "TessFlow", tool: "data_fetcher", retryCount: 2, timeout: 15, authStatus: "not_required" }, position: { x: 0, y: 150 } },
    { id: "n3", kind: "agent", title: "Process", description: "Analyze and process the data", status: "idle", config: { provider: "TessFlow", tool: "processor", authStatus: "not_required" }, position: { x: 0, y: 300 } },
    { id: "n4", kind: "output", title: "Output", description: "Send results to destination", status: "idle", config: { provider: "TessFlow", tool: "output_handler", authStatus: "not_required" }, position: { x: 0, y: 450 } },
  ],
  edges: [
    { id: "e1", source: "n1", target: "n2" },
    { id: "e2", source: "n2", target: "n3" },
    { id: "e3", source: "n3", target: "n4" },
  ],
};

// ─── Mock: Generate Workflow ─────────────────────────────────────────────────

function matchScenario(prompt: string): ScenarioTemplate {
  const lower = prompt.toLowerCase();
  for (const scenario of SCENARIOS) {
    const matchCount = scenario.keywords.filter((kw) => lower.includes(kw)).length;
    if (matchCount >= 2) return scenario;
  }
  return DEFAULT_SCENARIO;
}

export async function mockGenerateWorkflowFromPrompt(prompt: string): Promise<WorkflowDraft> {
  await delay(1200 + Math.random() * 800);

  const scenario = matchScenario(prompt);
  const ts = now();

  return {
    id: `wf-${uid()}`,
    name: scenario.name,
    description: scenario.description,
    status: "draft",
    nodes: scenario.nodes.map((n) => ({ ...n })),
    edges: scenario.edges.map((e) => ({ ...e })),
    assumptions: [...scenario.assumptions],
    unresolvedFields: [...scenario.unresolvedFields],
    createdAt: ts,
    updatedAt: ts,
  };
}

// ─── Mock: Patch Workflow ────────────────────────────────────────────────────

export async function mockPatchWorkflowFromInstruction(
  draft: WorkflowDraft,
  instruction: string
): Promise<WorkflowPatchResult> {
  await delay(800 + Math.random() * 600);

  const lower = instruction.toLowerCase();

  // Add approval before output
  if (lower.includes("add approval") || lower.includes("approval before")) {
    const outputNode = draft.nodes.find((n) => n.kind === "output");
    if (outputNode) {
      const newNode: FlowNode = {
        id: `n-${uid()}`,
        kind: "approval",
        title: "Approval Gate",
        description: "Require human approval before proceeding",
        status: "idle",
        config: { approvalRequired: true },
        position: { x: outputNode.position.x, y: outputNode.position.y - 75 },
      };

      // Shift the output node down
      const movedOutput: Partial<FlowNode> = {
        position: { x: outputNode.position.x, y: outputNode.position.y + 75 },
      };

      // Find edges going to the output node and reroute
      const incomingEdge = draft.edges.find((e) => e.target === outputNode.id);

      return {
        success: true,
        description: "Added an approval gate before the output node.",
        operations: [
          { type: "add_node", node: newNode, edges: [] },
          { type: "update_node", nodeId: outputNode.id, changes: movedOutput },
          ...(incomingEdge
            ? [
                { type: "remove_edge" as const, edgeId: incomingEdge.id },
                { type: "add_edge" as const, edge: { id: `e-${uid()}`, source: incomingEdge.source, target: newNode.id } },
                { type: "add_edge" as const, edge: { id: `e-${uid()}`, source: newNode.id, target: outputNode.id } },
              ]
            : []),
        ],
      };
    }
  }

  // Replace provider (e.g., "replace Telegram with Discord")
  if (lower.includes("replace") && lower.includes("with")) {
    const match = lower.match(/replace\s+(\w+)\s+with\s+(\w+)/);
    if (match) {
      const [, oldProv, newProv] = match;
      const targetNode = draft.nodes.find(
        (n) => n.config.provider?.toLowerCase() === oldProv || n.title.toLowerCase().includes(oldProv)
      );
      if (targetNode) {
        return {
          success: true,
          description: `Replaced ${oldProv} with ${newProv} in "${targetNode.title}".`,
          operations: [
            {
              type: "replace_provider",
              nodeId: targetNode.id,
              provider: newProv.charAt(0).toUpperCase() + newProv.slice(1),
              tool: `${newProv.toLowerCase()}_integration`,
            },
          ],
        };
      }
    }
  }

  // Change schedule
  if (lower.includes("schedule") || lower.includes("every")) {
    const triggerNode = draft.nodes.find((n) => n.kind === "trigger");
    if (triggerNode) {
      let newSchedule = "*/15 * * * *"; // default to every 15 min
      if (lower.includes("5 min")) newSchedule = "*/5 * * * *";
      else if (lower.includes("30 min")) newSchedule = "*/30 * * * *";
      else if (lower.includes("1 hour") || lower.includes("hourly")) newSchedule = "0 * * * *";
      else if (lower.includes("15 min")) newSchedule = "*/15 * * * *";

      return {
        success: true,
        description: `Updated schedule to ${newSchedule}.`,
        operations: [
          { type: "update_schedule", nodeId: triggerNode.id, schedule: newSchedule },
        ],
      };
    }
  }

  // Remove last output
  if (lower.includes("remove") && (lower.includes("output") || lower.includes("last"))) {
    const outputNodes = draft.nodes.filter((n) => n.kind === "output");
    const lastOutput = outputNodes[outputNodes.length - 1];
    if (lastOutput) {
      return {
        success: true,
        description: `Removed output node "${lastOutput.title}".`,
        operations: [{ type: "remove_node", nodeId: lastOutput.id }],
      };
    }
  }

  // Generic fallback — update description of first agent/tool node
  const editableNode = draft.nodes.find((n) => n.kind === "agent" || n.kind === "tool");
  if (editableNode) {
    return {
      success: true,
      description: `Updated "${editableNode.title}" based on your instruction.`,
      operations: [
        {
          type: "update_node",
          nodeId: editableNode.id,
          changes: {
            description: `${editableNode.description} (Updated: ${instruction})`,
            config: { ...editableNode.config, notes: instruction },
          },
        },
      ],
    };
  }

  return {
    success: false,
    description: "Could not interpret the edit instruction. Please be more specific.",
    operations: [],
  };
}

// ─── Mock: Validate Workflow ─────────────────────────────────────────────────

export async function mockValidateWorkflow(draft: WorkflowDraft): Promise<ValidationResult> {
  await delay(600 + Math.random() * 400);

  const issues: ValidationResult["issues"] = [];

  // Check for disconnected integrations
  for (const node of draft.nodes) {
    if (node.config.authStatus === "disconnected") {
      issues.push({
        id: `vi-${uid()}`,
        nodeId: node.id,
        severity: "warning",
        message: `"${node.title}" has a disconnected integration (${node.config.provider}).`,
        suggestion: "Connect the integration in Settings → Integrations.",
      });
    }
  }

  // Check for unresolved fields
  if (draft.unresolvedFields.length > 0) {
    for (const field of draft.unresolvedFields) {
      issues.push({
        id: `vi-${uid()}`,
        severity: "warning",
        message: `Unresolved field: ${field}`,
        suggestion: "Provide the required value in the inspector panel.",
      });
    }
  }

  // Check for nodes without connections
  for (const node of draft.nodes) {
    const hasIncoming = draft.edges.some((e) => e.target === node.id);
    const hasOutgoing = draft.edges.some((e) => e.source === node.id);
    if (!hasIncoming && !hasOutgoing) {
      issues.push({
        id: `vi-${uid()}`,
        nodeId: node.id,
        severity: "error",
        message: `"${node.title}" is disconnected from the workflow.`,
        suggestion: "Connect this node to the rest of the workflow.",
      });
    }
  }

  // Check trigger exists
  const hasTrigger = draft.nodes.some((n) => n.kind === "trigger");
  if (!hasTrigger) {
    issues.push({
      id: `vi-${uid()}`,
      severity: "error",
      message: "Workflow has no trigger node.",
      suggestion: "Add a trigger to define when the workflow starts.",
    });
  }

  // Check output exists
  const hasOutput = draft.nodes.some((n) => n.kind === "output");
  if (!hasOutput) {
    issues.push({
      id: `vi-${uid()}`,
      severity: "info",
      message: "Workflow has no output node.",
      suggestion: "Consider adding an output to capture results.",
    });
  }

  return {
    valid: issues.every((i) => i.severity !== "error"),
    issues,
  };
}

// ─── Mock: Run Workflow ──────────────────────────────────────────────────────

export async function mockRunWorkflow(
  draft: WorkflowDraft,
  onEvent: (event: ExecutionEvent) => void
): Promise<void> {
  // Build execution order from edges (simple topological sort)
  const executionOrder = buildExecutionOrder(draft);

  // Start event
  onEvent({
    id: `ev-${uid()}`,
    type: "started",
    message: `Execution started for "${draft.name}"`,
    timestamp: now(),
  });

  for (const node of executionOrder) {
    // Node started
    onEvent({
      id: `ev-${uid()}`,
      type: "node_started",
      nodeId: node.id,
      nodeName: node.title,
      message: `Running "${node.title}"...`,
      timestamp: now(),
    });

    // Simulate processing time
    await delay(800 + Math.random() * 1200);

    // Approval nodes pause
    if (node.kind === "approval") {
      onEvent({
        id: `ev-${uid()}`,
        type: "waiting_for_approval",
        nodeId: node.id,
        nodeName: node.title,
        message: `Waiting for approval at "${node.title}"`,
        timestamp: now(),
      });

      // Auto-approve after delay (simulated)
      await delay(2000);

      onEvent({
        id: `ev-${uid()}`,
        type: "approval_granted",
        nodeId: node.id,
        nodeName: node.title,
        message: `Approval granted for "${node.title}"`,
        timestamp: now(),
      });
    }

    // Simulate failure for specific scenario
    if (node.config.authStatus === "disconnected" && node.kind === "output") {
      onEvent({
        id: `ev-${uid()}`,
        type: "node_failed",
        nodeId: node.id,
        nodeName: node.title,
        message: `Failed: "${node.title}" — integration not connected (${node.config.provider})`,
        timestamp: now(),
      });

      onEvent({
        id: `ev-${uid()}`,
        type: "failed",
        message: `Execution failed at "${node.title}"`,
        timestamp: now(),
      });
      return;
    }

    // Node completed
    onEvent({
      id: `ev-${uid()}`,
      type: "node_completed",
      nodeId: node.id,
      nodeName: node.title,
      message: `Completed "${node.title}" successfully`,
      timestamp: now(),
    });
  }

  // All done
  onEvent({
    id: `ev-${uid()}`,
    type: "completed",
    message: `Execution completed for "${draft.name}"`,
    timestamp: now(),
  });
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function buildExecutionOrder(draft: WorkflowDraft): FlowNode[] {
  const nodeMap = new Map(draft.nodes.map((n) => [n.id, n]));
  const visited = new Set<string>();
  const result: FlowNode[] = [];
  const adjacency = new Map<string, string[]>();

  for (const edge of draft.edges) {
    if (!adjacency.has(edge.source)) adjacency.set(edge.source, []);
    adjacency.get(edge.source)!.push(edge.target);
  }

  // Find root nodes (no incoming edges)
  const hasIncoming = new Set(draft.edges.map((e) => e.target));
  const roots = draft.nodes.filter((n) => !hasIncoming.has(n.id));

  function dfs(nodeId: string) {
    if (visited.has(nodeId)) return;
    visited.add(nodeId);
    const node = nodeMap.get(nodeId);
    if (node) result.push(node);
    const children = adjacency.get(nodeId) || [];
    for (const child of children) dfs(child);
  }

  for (const root of roots) dfs(root.id);

  // Add any remaining unvisited nodes
  for (const node of draft.nodes) {
    if (!visited.has(node.id)) result.push(node);
  }

  return result;
}

// ─── Demo Prompts ────────────────────────────────────────────────────────────

export const DEMO_PROMPTS = [
  "Monitor top wallets buying new Solana meme coins and alert me on Telegram if 3+ tracked wallets buy the same token",
  "Summarize new governance proposals every hour and send high-priority ones to Discord",
  "Watch smart money swaps and create a follow-up task when unusual activity is detected",
];
