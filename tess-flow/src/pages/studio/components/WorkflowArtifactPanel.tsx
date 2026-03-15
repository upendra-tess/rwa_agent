/**
 * WorkflowArtifactPanel — Right-side artifact showing workflow canvas + inspector.
 * Appears like Claude/ChatGPT artifacts when a workflow is generated.
 */
import { X, Maximize2, Minimize2, Settings2 } from "lucide-react";
import WorkflowCanvas from "./WorkflowCanvas";
import WorkflowInspector from "./WorkflowInspector";
import WorkflowToolbar from "./WorkflowToolbar";
import type { WorkflowDraft, ValidationIssue, FlowNodeConfig, ExecutionStatus } from "../lib/types";

interface WorkflowArtifactPanelProps {
  draft: WorkflowDraft | null;
  selectedNodeId: string | null;
  selectedNode: any;
  validationIssues: ValidationIssue[];
  executionStatus: ExecutionStatus;
  isValidating: boolean;
  isOpen: boolean;
  isFullscreen: boolean;
  showInspector: boolean;
  onSelectNode: (nodeId: string | null) => void;
  onUpdateNodeConfig: (nodeId: string, config: Partial<FlowNodeConfig>) => void;
  onUpdateNodeField: (nodeId: string, field: "title" | "description", value: string) => void;
  onValidate: () => void;
  onRun: () => void;
  onSaveDraft: () => void;
  onReset: () => void;
  onClose: () => void;
  onToggleFullscreen: () => void;
  onToggleInspector: () => void;
}

const WorkflowArtifactPanel = ({
  draft,
  selectedNodeId,
  selectedNode,
  validationIssues,
  executionStatus,
  isValidating,
  isOpen,
  isFullscreen,
  showInspector,
  onSelectNode,
  onUpdateNodeConfig,
  onUpdateNodeField,
  onValidate,
  onRun,
  onSaveDraft,
  onReset,
  onClose,
  onToggleFullscreen,
  onToggleInspector,
}: WorkflowArtifactPanelProps) => {
  if (!isOpen || !draft) return null;

  return (
    <div className={`studio-artifact-panel ${isFullscreen ? "fullscreen" : ""}`}>
      {/* Toolbar */}
      <div className="studio-artifact-toolbar">
        <div className="studio-artifact-toolbar-left">
          <span className="studio-artifact-title">{draft.name}</span>
        </div>
        <div className="studio-artifact-toolbar-actions">
          <button
            type="button"
            className="studio-artifact-icon-btn"
            onClick={onToggleInspector}
            title={showInspector ? "Hide inspector" : "Show inspector"}
          >
            <Settings2 size={14} strokeWidth={2} />
          </button>
          <button
            type="button"
            className="studio-artifact-icon-btn"
            onClick={onToggleFullscreen}
            title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
          >
            {isFullscreen ? <Minimize2 size={14} strokeWidth={2} /> : <Maximize2 size={14} strokeWidth={2} />}
          </button>
          <button
            type="button"
            className="studio-artifact-icon-btn"
            onClick={onClose}
            title="Close"
          >
            <X size={14} strokeWidth={2} />
          </button>
        </div>
      </div>

      {/* Workflow toolbar */}
      <WorkflowToolbar
        workflowName={draft.name}
        workflowStatus={draft.status}
        executionStatus={executionStatus}
        issueCount={validationIssues.length}
        isValidating={isValidating}
        onValidate={onValidate}
        onRun={onRun}
        onSaveDraft={onSaveDraft}
        onReset={onReset}
        disabled={false}
      />

      {/* Canvas + Inspector */}
      <div className="studio-artifact-body">
        <div className="studio-artifact-canvas">
          <WorkflowCanvas
            draft={draft}
            selectedNodeId={selectedNodeId}
            onSelectNode={onSelectNode}
          />
        </div>

        {showInspector && (
          <div className="studio-artifact-inspector">
            <WorkflowInspector
              draft={draft}
              selectedNode={selectedNode}
              validationIssues={validationIssues}
              onUpdateNodeConfig={onUpdateNodeConfig}
              onUpdateNodeField={onUpdateNodeField}
            />
          </div>
        )}
      </div>
    </div>
  );
};

export default WorkflowArtifactPanel;
