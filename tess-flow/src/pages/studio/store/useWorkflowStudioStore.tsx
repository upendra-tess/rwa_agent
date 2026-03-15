/**
 * TessFlow Studio — State management.
 * Simple reactive store using React hooks for workflow studio state.
 */

import { useState, useCallback, useMemo } from "react";
import type {
  WorkflowDraft,
  StudioChatMessage,
  ValidationIssue,
  ExecutionEvent,
  ExecutionStatus,
  FlowNode,
  NodeStatus,
  WorkflowStatus,
} from "../lib/types";

// ─── Store State ─────────────────────────────────────────────────────────────

interface WorkflowStudioState {
  // Core workflow
  currentWorkflowDraft: WorkflowDraft | null;
  selectedNodeId: string | null;
  
  // Chat
  chatMessages: StudioChatMessage[];
  isGenerating: boolean;
  
  // Validation
  validationIssues: ValidationIssue[];
  
  // Execution
  executionStatus: ExecutionStatus;
  executionEvents: ExecutionEvent[];
  
  // UI state
  isValidating: boolean;
  isResetting: boolean;
}

const INITIAL_STATE: WorkflowStudioState = {
  currentWorkflowDraft: null,
  selectedNodeId: null,
  chatMessages: [],
  isGenerating: false,
  validationIssues: [],
  executionStatus: "idle",
  executionEvents: [],
  isValidating: false,
  isResetting: false,
};

// ─── Store Hook ──────────────────────────────────────────────────────────────

export const useWorkflowStudioStore = () => {
  const [state, setState] = useState<WorkflowStudioState>(INITIAL_STATE);

  // ── Actions ──

  const addChatMessage = useCallback((message: StudioChatMessage) => {
    setState((prev) => ({
      ...prev,
      chatMessages: [...prev.chatMessages, message],
    }));
  }, []);

  const setIsGenerating = useCallback((isGenerating: boolean) => {
    setState((prev) => ({ ...prev, isGenerating }));
  }, []);

  const setWorkflowDraft = useCallback((draft: WorkflowDraft | null) => {
    setState((prev) => ({
      ...prev,
      currentWorkflowDraft: draft,
      selectedNodeId: null, // Clear selection when workflow changes
    }));
  }, []);

  const updateWorkflowDraft = useCallback((updates: Partial<WorkflowDraft>) => {
    setState((prev) => ({
      ...prev,
      currentWorkflowDraft: prev.currentWorkflowDraft
        ? { ...prev.currentWorkflowDraft, ...updates, updatedAt: new Date().toISOString() }
        : null,
    }));
  }, []);

  const updateNodeConfig = useCallback((nodeId: string, configUpdates: Partial<FlowNode["config"]>) => {
    setState((prev) => {
      if (!prev.currentWorkflowDraft) return prev;
      
      const updatedNodes = prev.currentWorkflowDraft.nodes.map((node) =>
        node.id === nodeId
          ? { ...node, config: { ...node.config, ...configUpdates } }
          : node
      );
      
      return {
        ...prev,
        currentWorkflowDraft: {
          ...prev.currentWorkflowDraft,
          nodes: updatedNodes,
          updatedAt: new Date().toISOString(),
        },
      };
    });
  }, []);

  const updateNodeStatus = useCallback((nodeId: string, status: NodeStatus, error?: string) => {
    setState((prev) => {
      if (!prev.currentWorkflowDraft) return prev;
      
      const updatedNodes = prev.currentWorkflowDraft.nodes.map((node) =>
        node.id === nodeId
          ? { ...node, status, error }
          : node
      );
      
      return {
        ...prev,
        currentWorkflowDraft: {
          ...prev.currentWorkflowDraft,
          nodes: updatedNodes,
        },
      };
    });
  }, []);

  const setSelectedNodeId = useCallback((nodeId: string | null) => {
    setState((prev) => ({ ...prev, selectedNodeId: nodeId }));
  }, []);

  const setValidationIssues = useCallback((issues: ValidationIssue[]) => {
    setState((prev) => ({ ...prev, validationIssues: issues }));
  }, []);

  const setIsValidating = useCallback((isValidating: boolean) => {
    setState((prev) => ({ ...prev, isValidating }));
  }, []);

  const setExecutionStatus = useCallback((status: ExecutionStatus) => {
    setState((prev) => ({ ...prev, executionStatus: status }));
  }, []);

  const addExecutionEvent = useCallback((event: ExecutionEvent) => {
    setState((prev) => ({
      ...prev,
      executionEvents: [...prev.executionEvents, event],
    }));
  }, []);

  const updateWorkflowStatus = useCallback((status: WorkflowStatus) => {
    setState((prev) => ({
      ...prev,
      currentWorkflowDraft: prev.currentWorkflowDraft
        ? { ...prev.currentWorkflowDraft, status, updatedAt: new Date().toISOString() }
        : null,
    }));
  }, []);

  const resetWorkflow = useCallback(() => {
    setState((prev) => ({
      ...INITIAL_STATE,
      chatMessages: prev.chatMessages, // Keep chat history
    }));
  }, []);

  const resetAll = useCallback(() => {
    setState(INITIAL_STATE);
  }, []);

  // ── Computed values ──

  const selectedNode = useMemo(() => {
    return state.currentWorkflowDraft?.nodes.find(node => node.id === state.selectedNodeId) || null;
  }, [state.currentWorkflowDraft, state.selectedNodeId]);

  const hasWorkflow = useMemo(() => {
    return !!state.currentWorkflowDraft;
  }, [state.currentWorkflowDraft]);

  const isWorkflowValid = useMemo(() => {
    return state.validationIssues.every(issue => issue.severity !== "error");
  }, [state.validationIssues]);

  const canRun = useMemo(() => {
    return hasWorkflow && isWorkflowValid && state.executionStatus === "idle";
  }, [hasWorkflow, isWorkflowValid, state.executionStatus]);

  return {
    // State
    ...state,
    
    // Computed
    selectedNode,
    hasWorkflow,
    isWorkflowValid,
    canRun,
    
    // Actions
    addChatMessage,
    setIsGenerating,
    setWorkflowDraft,
    updateWorkflowDraft,
    updateNodeConfig,
    updateNodeStatus,
    setSelectedNodeId,
    setValidationIssues,
    setIsValidating,
    setExecutionStatus,
    addExecutionEvent,
    updateWorkflowStatus,
    resetWorkflow,
    resetAll,
  };
};

// ─── Store Provider Context (Optional) ───────────────────────────────────────

import React, { createContext, useContext, ReactNode } from "react";

type WorkflowStudioStore = ReturnType<typeof useWorkflowStudioStore>;

const WorkflowStudioStoreContext = createContext<WorkflowStudioStore | null>(null);

interface WorkflowStudioStoreProviderProps {
  children: ReactNode;
}

export const WorkflowStudioStoreProvider: React.FC<WorkflowStudioStoreProviderProps> = ({ children }) => {
  const store = useWorkflowStudioStore();
  
  return (
    <WorkflowStudioStoreContext.Provider value={store}>
      {children}
    </WorkflowStudioStoreContext.Provider>
  );
};

export const useWorkflowStudioStoreContext = () => {
  const context = useContext(WorkflowStudioStoreContext);
  if (!context) {
    throw new Error("useWorkflowStudioStoreContext must be used within WorkflowStudioStoreProvider");
  }
  return context;
};