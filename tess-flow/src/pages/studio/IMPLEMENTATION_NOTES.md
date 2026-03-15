# TessFlow Workflow Studio — Implementation Notes

## What Was Built

A production-grade, chat-driven workflow builder page integrated into the existing TessFlow app as a new navigation view.

---

## Files Added / Changed

### New Files — Studio Feature

| Path | Purpose |
|---|---|
| `src/pages/studio/lib/types.ts` | All TypeScript types: `WorkflowDraft`, `FlowNode`, `FlowEdge`, `StudioChatMessage`, `ExecutionEvent`, `ValidationIssue`, `PatchOperation`, status enums |
| `src/pages/studio/lib/mockOrchestrator.ts` | Mock adapters: `mockGenerateWorkflowFromPrompt`, `mockPatchWorkflowFromInstruction`, `mockValidateWorkflow`, `mockRunWorkflow` |
| `src/pages/studio/store/useWorkflowStudioStore.tsx` | Zustand store — single source of truth for all workflow/chat/execution state |
| `src/pages/studio/components/WorkflowChatPanel.tsx` | Left panel: chat thread, composer, proposal cards, validation cards, execution event cards |
| `src/pages/studio/components/WorkflowCanvas.tsx` | Center panel: React Flow canvas with custom node types, empty state, controls |
| `src/pages/studio/components/nodes/WorkflowNode.tsx` | Custom React Flow node component supporting all 7 node kinds with status highlighting |
| `src/pages/studio/components/WorkflowInspector.tsx` | Right panel: per-node editable config and workflow-level overview |
| `src/pages/studio/components/WorkflowToolbar.tsx` | Top action bar: status badge, Validate / Run / Save / Reset buttons |
| `src/pages/studio/WorkflowStudioPage.tsx` | Root page component; orchestrates all panels and wires mock adapters to store |
| `src/pages/studio/IMPLEMENTATION_NOTES.md` | This file |

### Modified Files — App Integration

| Path | Change |
|---|---|
| `src/types/index.ts` | Added `"studio"` to `AppView` union |
| `src/layout/LeftDock.tsx` | Added "Workflow Studio" nav item with `Workflow` icon; removed unused `User` import |
| `src/layout/AppHeader.tsx` | Added `studio` entry to `VIEW_TITLES`; removed unused `Search` import |
| `src/App.tsx` | Imported `WorkflowStudioPage`; added `{view === "studio" && <WorkflowStudioPage />}` render branch |
| `src/index.css` | Added ~700 lines of scoped studio CSS (all prefixed `.studio-*`, `.wf-*`, `.inspector-*`) |

---

## State Flow

```
User types prompt
  → WorkflowChatPanel.onSubmitPrompt(text)
    → WorkflowStudioPage.handleSubmitPrompt(text)
      ├─ (no draft) → mockGenerateWorkflowFromPrompt(text)
      │   → store.setWorkflowDraft(draft)          ← canvas re-renders
      │   → store.addChatMessage(proposal card)    ← chat shows card
      └─ (draft exists) → mockPatchWorkflowFromInstruction(draft, text)
          → applyPatchOperations(draft, ops)
          → store.setWorkflowDraft(patched)         ← canvas updates in place
          → store.addChatMessage(assistant confirm)

User clicks Validate
  → WorkflowStudioPage.handleValidate()
    → mockValidateWorkflow(draft)
      → store.setValidationIssues(issues)
      → store.updateWorkflowStatus("ready" | "needs_input")
      → store.addChatMessage(validation summary card)

User clicks Run
  → WorkflowStudioPage.handleRun()
    → mockRunWorkflow(draft, onEvent)
      → onEvent called sequentially per node:
          → store.updateNodeStatus(nodeId, status)  ← node highlights on canvas
          → store.addExecutionEvent(event)
          → store.addChatMessage(execution event card)
      → workflow status → "completed" | "failed" | "paused_for_approval"

User selects a node on canvas
  → ReactFlow.onNodeClick → store.setSelectedNodeId(id)
    → WorkflowInspector renders selected node's editable fields
      → inspector onChange → store.updateNodeConfig / updateWorkflowDraft
```

---

## Mock Orchestrator — How It Works

All mocks live in `lib/mockOrchestrator.ts` and are intentionally deterministic:

### `mockGenerateWorkflowFromPrompt(prompt)`
- Matches the prompt text against 4 scenario patterns (wallet monitor, governance, smart money, generic research+notify)
- Returns a fully-typed `WorkflowDraft` with realistic nodes, edges, assumptions, and unresolved fields
- 1.5–2s simulated latency

### `mockPatchWorkflowFromInstruction(draft, instruction)`
- Detects edit intent via keyword matching: approval, discord/telegram/slack replace, schedule change, condition, remove output
- Returns `PatchOperation[]` — a typed list of graph mutations (add_node, remove_node, update_node, replace_provider, update_schedule, add/remove_edge)
- The page applies these operations immutably without replacing the whole draft

### `mockValidateWorkflow(draft)`
- Checks for disconnected nodes, missing auth, and unresolved fields
- Returns `ValidationResult` with `issues[]` typed as `error | warning | info`

### `mockRunWorkflow(draft, onEvent)`
- Steps through nodes in topological order (by edge connections)
- Emits `ExecutionEvent` objects via the callback: node_started → node_completed (or node_failed for the first tool node when "fail" scenario is detected)
- Pauses 500ms between events to animate the canvas
- If an `approval` node is encountered, emits `waiting_for_approval` then auto-continues after 3s (simulating operator approval)

---

## Replacing Mocks With Real APIs

All mock functions share the same signatures as their production counterparts would. To swap:

```ts
// lib/mockOrchestrator.ts  →  lib/orchestratorClient.ts

export async function mockGenerateWorkflowFromPrompt(prompt: string): Promise<WorkflowDraft> {
  // swap: return orchestratorClient.post("/workflows/generate", { prompt })
}

export async function mockPatchWorkflowFromInstruction(
  draft: WorkflowDraft,
  instruction: string
): Promise<WorkflowPatchResult> {
  // swap: return orchestratorClient.post("/workflows/patch", { draft, instruction })
}

export async function mockValidateWorkflow(draft: WorkflowDraft): Promise<ValidationResult> {
  // swap: return orchestratorClient.post("/workflows/validate", { draft })
}

export async function mockRunWorkflow(
  draft: WorkflowDraft,
  onEvent: (event: ExecutionEvent) => void
): Promise<void> {
  // swap: open WebSocket to /workflows/run and pipe events to onEvent callback
}
```

The store, components, and page logic require **zero changes** — only the adapter layer needs replacing.

---

## Node Kinds Supported

| Kind | Icon | Color |
|---|---|---|
| `trigger` | Zap | Teal |
| `tool` | Wrench | Blue |
| `agent` | Bot | Purple |
| `condition` | GitBranch | Amber |
| `approval` | Shield | Orange |
| `transform` | Settings2 | Slate |
| `output` | Send | Green |

---

## Demo Prompts (Built In)

1. Monitor top wallets buying new Solana meme coins and alert me on Telegram if 3 tracked wallets buy the same token
2. Summarize new governance proposals every hour and send high-priority ones to Discord
3. Watch smart money swaps and create a follow-up task when unusual activity is detected
4. Research the top 5 trending AI agents and send a briefing to Slack every morning

All are available as quick-action chips in the chat welcome state.
