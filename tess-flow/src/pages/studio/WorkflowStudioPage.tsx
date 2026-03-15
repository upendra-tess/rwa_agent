/**
 * WorkflowStudioPage — TessFlow's chat-driven workflow builder.
 * ChatGPT-style layout: History sidebar | Chat center | Workflow artifact
 */
import { useCallback, useRef, useState } from "react";
import { PanelLeft } from "lucide-react";
import { useWorkflowStudioStore } from "./store/useWorkflowStudioStore";
import {
  mockGenerateWorkflowFromPrompt,
  mockPatchWorkflowFromInstruction,
  mockValidateWorkflow,
  mockRunWorkflow,
} from "./lib/mockOrchestrator";
import type {
  StudioChatMessage,
  FlowNode,
  FlowNodeConfig,
  ExecutionEvent,
  PatchOperation,
  WorkflowDraft,
} from "./lib/types";
import ConversationHistorySidebar, { type WorkflowConversation } from "./components/ConversationHistorySidebar";
import StudioChatInterface from "./components/StudioChatInterface";
import WorkflowArtifactPanel from "./components/WorkflowArtifactPanel";

// ─── Helpers ─────────────────────────────────────────────────────────────────

const makeId = () => `msg-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
const now = () => new Date().toISOString();

function makeSystemNotice(text: string): StudioChatMessage {
  return { id: makeId(), kind: "system_notice", text, timestamp: now() };
}

function applyPatchOperations(draft: WorkflowDraft, operations: PatchOperation[]): WorkflowDraft {
  let nodes = [...draft.nodes];
  let edges = [...draft.edges];

  for (const op of operations) {
    if (op.type === "add_node") {
      nodes = [...nodes, op.node];
      edges = [...edges, ...op.edges];
    } else if (op.type === "remove_node") {
      nodes = nodes.filter((n) => n.id !== op.nodeId);
      edges = edges.filter((e) => e.source !== op.nodeId && e.target !== op.nodeId);
    } else if (op.type === "update_node") {
      nodes = nodes.map((n) => (n.id === op.nodeId ? { ...n, ...op.changes } : n));
    } else if (op.type === "replace_provider") {
      nodes = nodes.map((n) =>
        n.id === op.nodeId
          ? { ...n, config: { ...n.config, provider: op.provider, tool: op.tool, authStatus: "disconnected" as const } }
          : n
      );
    } else if (op.type === "update_schedule") {
      nodes = nodes.map((n) =>
        n.id === op.nodeId
          ? { ...n, config: { ...n.config, schedule: op.schedule } }
          : n
      );
    } else if (op.type === "add_edge") {
      edges = [...edges, op.edge];
    } else if (op.type === "remove_edge") {
      edges = edges.filter((e) => e.id !== op.edgeId);
    }
  }

  return { ...draft, nodes, edges, updatedAt: now() };
}

// ─── Main Component ───────────────────────────────────────────────────────────

const WorkflowStudioPage = () => {
  const store = useWorkflowStudioStore();
  const executionRunningRef = useRef(false);
  
  // UI state
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isArtifactOpen, setIsArtifactOpen] = useState(false);
  const [isArtifactFullscreen, setIsArtifactFullscreen] = useState(false);
  const [showInspector, setShowInspector] = useState(true);
  
  // Conversation management (simplified for now)
  const [conversations, setConversations] = useState<WorkflowConversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);

  // ── Handlers ──────────────────────────────────────────────────────────────

  const handleSubmitPrompt = useCallback(async (prompt: string) => {
    if (store.isGenerating) return;

    store.addChatMessage({
      id: makeId(),
      kind: "user",
      text: prompt,
      timestamp: now(),
    });

    store.setIsGenerating(true);

    try {
      if (store.currentWorkflowDraft) {
        const patchResult = await mockPatchWorkflowFromInstruction(store.currentWorkflowDraft, prompt);

        if (patchResult.success && patchResult.operations.length > 0) {
          const patched = applyPatchOperations(store.currentWorkflowDraft, patchResult.operations);
          store.setWorkflowDraft(patched);
          store.addChatMessage({
            id: makeId(),
            kind: "assistant_text",
            text: `✓ ${patchResult.description}`,
            timestamp: now(),
          });
          store.setValidationIssues([]);
        } else {
          store.addChatMessage({
            id: makeId(),
            kind: "assistant_text",
            text: patchResult.description,
            timestamp: now(),
          });
        }
      } else {
        store.addChatMessage(makeSystemNotice("Generating workflow from your prompt…"));

        const draft = await mockGenerateWorkflowFromPrompt(prompt);
        store.setWorkflowDraft(draft);
        setIsArtifactOpen(true);

        store.addChatMessage({
          id: makeId(),
          kind: "workflow_proposal",
          text: "I've generated a workflow based on your request. Here's what I created:",
          workflowSummary: `${draft.name} — ${draft.description}`,
          assumptions: draft.assumptions,
          unresolvedFields: draft.unresolvedFields,
          timestamp: now(),
        });
      }
    } catch (err) {
      store.addChatMessage({
        id: makeId(),
        kind: "assistant_text",
        text: "Something went wrong generating the workflow. Please try again.",
        timestamp: now(),
      });
    } finally {
      store.setIsGenerating(false);
    }
  }, [store]);

  const handleValidate = useCallback(async () => {
    if (!store.currentWorkflowDraft || store.isValidating) return;

    store.setIsValidating(true);
    store.addChatMessage(makeSystemNotice("Running validation…"));

    try {
      const result = await mockValidateWorkflow(store.currentWorkflowDraft);
      store.setValidationIssues(result.issues);
      store.updateWorkflowStatus(result.valid ? "ready" : "needs_input");

      store.addChatMessage({
        id: makeId(),
        kind: "validation_summary",
        text: result.valid ? "Validation passed — workflow is ready to run." : "Validation found issues.",
        validationResult: result,
        timestamp: now(),
      });
    } catch (err) {
      store.addChatMessage({
        id: makeId(),
        kind: "assistant_text",
        text: "Validation failed unexpectedly.",
        timestamp: now(),
      });
    } finally {
      store.setIsValidating(false);
    }
  }, [store]);

  const handleRun = useCallback(async () => {
    if (!store.currentWorkflowDraft || executionRunningRef.current) return;

    executionRunningRef.current = true;
    store.setExecutionStatus("running");
    store.updateWorkflowStatus("running");

    const resetNodes = store.currentWorkflowDraft.nodes.map((n) => ({
      ...n,
      status: "idle" as const,
      error: undefined,
    }));
    store.updateWorkflowDraft({ nodes: resetNodes });

    store.addChatMessage(makeSystemNotice("Starting workflow execution simulation…"));

    try {
      await mockRunWorkflow(
        store.currentWorkflowDraft,
        (event: ExecutionEvent) => {
          store.addExecutionEvent(event);

          store.addChatMessage({
            id: makeId(),
            kind: "execution_event",
            text: event.message,
            executionEvent: event,
            timestamp: event.timestamp,
          });

          if (event.nodeId) {
            if (event.type === "node_started") {
              store.updateNodeStatus(event.nodeId, "running");
            } else if (event.type === "node_completed") {
              store.updateNodeStatus(event.nodeId, "success");
            } else if (event.type === "node_failed") {
              store.updateNodeStatus(event.nodeId, "error", event.message);
            } else if (event.type === "waiting_for_approval") {
              store.updateNodeStatus(event.nodeId, "waiting");
              store.updateWorkflowStatus("paused_for_approval");
            } else if (event.type === "approval_granted") {
              store.updateNodeStatus(event.nodeId, "success");
              store.updateWorkflowStatus("running");
            }
          }

          if (event.type === "completed") {
            store.setExecutionStatus("completed");
            store.updateWorkflowStatus("completed");
          } else if (event.type === "failed") {
            store.setExecutionStatus("failed");
            store.updateWorkflowStatus("failed");
          }
        }
      );
    } catch (err) {
      store.setExecutionStatus("failed");
      store.updateWorkflowStatus("failed");
      store.addChatMessage({
        id: makeId(),
        kind: "assistant_text",
        text: "Execution failed unexpectedly.",
        timestamp: now(),
      });
    } finally {
      executionRunningRef.current = false;
    }
  }, [store]);

  const handleSaveDraft = useCallback(() => {
    if (!store.currentWorkflowDraft) return;
    try {
      localStorage.setItem(
        `tessflow-draft-${store.currentWorkflowDraft.id}`,
        JSON.stringify(store.currentWorkflowDraft)
      );
      store.addChatMessage(makeSystemNotice("Draft saved to local storage."));
    } catch {
      store.addChatMessage(makeSystemNotice("Could not save draft."));
    }
  }, [store]);

  const handleReset = useCallback(() => {
    executionRunningRef.current = false;
    store.resetAll();
    setIsArtifactOpen(false);
  }, [store]);

  const handleUpdateNodeConfig = useCallback((nodeId: string, config: Partial<FlowNodeConfig>) => {
    store.updateNodeConfig(nodeId, config);
  }, [store]);

  const handleUpdateNodeField = useCallback((nodeId: string, field: "title" | "description", value: string) => {
    if (!store.currentWorkflowDraft) return;
    const updatedNodes = store.currentWorkflowDraft.nodes.map((n: FlowNode) =>
      n.id === nodeId ? { ...n, [field]: value } : n
    );
    store.updateWorkflowDraft({ nodes: updatedNodes });
  }, [store]);

  const handleShowWorkflow = useCallback(() => {
    setIsArtifactOpen(true);
  }, []);

  const handleNewConversation = useCallback(() => {
    store.resetAll();
    setIsArtifactOpen(false);
    setActiveConversationId(null);
  }, [store]);

  const hasWorkflow = !!store.currentWorkflowDraft;

  return (
    <div className="studio-layout-v2">
      {/* Sidebar */}
      <ConversationHistorySidebar
        conversations={conversations}
        activeId={activeConversationId}
        isOpen={isSidebarOpen}
        onToggle={() => setIsSidebarOpen(!isSidebarOpen)}
        onSelect={setActiveConversationId}
        onNew={handleNewConversation}
        onDelete={(id) => setConversations((prev) => prev.filter((c) => c.id !== id))}
      />

      {/* Sidebar toggle button */}
      <button
        type="button"
        className={`studio-sidebar-toggle ${!isSidebarOpen ? "visible" : ""}`}
        onClick={() => setIsSidebarOpen(true)}
        aria-label="Open conversation history"
        title="Open conversation history"
      >
        <PanelLeft size={18} strokeWidth={1.7} />
      </button>

      {/* Main chat area */}
      <div className={`studio-main-area ${isArtifactOpen ? "with-artifact" : ""}`}>
        <StudioChatInterface
          messages={store.chatMessages}
          isGenerating={store.isGenerating}
          hasWorkflow={hasWorkflow}
          onSubmitPrompt={handleSubmitPrompt}
          onShowWorkflow={handleShowWorkflow}
          onValidate={handleValidate}
          onRun={handleRun}
        />
      </div>

      {/* Workflow artifact */}
      <WorkflowArtifactPanel
        draft={store.currentWorkflowDraft}
        selectedNodeId={store.selectedNodeId}
        selectedNode={store.selectedNode}
        validationIssues={store.validationIssues}
        executionStatus={store.executionStatus}
        isValidating={store.isValidating}
        isOpen={isArtifactOpen}
        isFullscreen={isArtifactFullscreen}
        showInspector={showInspector}
        onSelectNode={store.setSelectedNodeId}
        onUpdateNodeConfig={handleUpdateNodeConfig}
        onUpdateNodeField={handleUpdateNodeField}
        onValidate={handleValidate}
        onRun={handleRun}
        onSaveDraft={handleSaveDraft}
        onReset={handleReset}
        onClose={() => setIsArtifactOpen(false)}
        onToggleFullscreen={() => setIsArtifactFullscreen(!isArtifactFullscreen)}
        onToggleInspector={() => setShowInspector(!showInspector)}
      />
    </div>
  );
};

export default WorkflowStudioPage;
