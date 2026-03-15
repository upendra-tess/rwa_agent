/**
 * WorkflowCanvas — React Flow-based canvas for workflow visualization.
 */
import { useCallback, useMemo, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  BackgroundVariant,
  type Connection,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Workflow, MousePointerClick } from "lucide-react";
import WorkflowNode, { type WorkflowNodeData } from "./nodes/WorkflowNode";
import type { WorkflowDraft, FlowNode } from "../lib/types";

// ─── Node types registry ──────────────────────────────────────────────────────

const NODE_TYPES = { workflowNode: WorkflowNode };

// ─── Mapper: FlowNode → React Flow Node ─────────────────────────────────────

function mapToRFNode(node: FlowNode, selectedId: string | null): Node<WorkflowNodeData> {
  return {
    id: node.id,
    type: "workflowNode",
    position: node.position,
    data: {
      kind: node.kind,
      title: node.title,
      description: node.description,
      status: node.status,
      config: node.config,
      error: node.error,
      isSelected: node.id === selectedId,
    },
  };
}

function mapToRFEdge(edge: { id: string; source: string; target: string; label?: string; animated?: boolean }): Edge {
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.label,
    animated: edge.animated,
    style: {
      stroke: "rgba(0,248,250,0.25)",
      strokeWidth: 1.5,
    },
    labelStyle: {
      fill: "var(--text-muted)",
      fontSize: 11,
      fontFamily: "'Exo 2', sans-serif",
    },
    labelBgStyle: {
      fill: "rgba(5,8,10,0.85)",
      stroke: "rgba(255,255,255,0.06)",
    },
    labelBgBorderRadius: 6,
    labelBgPadding: [4, 8] as [number, number],
  };
}

// ─── Props ───────────────────────────────────────────────────────────────────

interface WorkflowCanvasProps {
  draft: WorkflowDraft | null;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string | null) => void;
}

// ─── Empty state ─────────────────────────────────────────────────────────────

function CanvasEmptyState() {
  return (
    <div className="wf-canvas-empty">
      <div className="wf-canvas-empty-icon">
        <Workflow size={32} strokeWidth={1.2} />
      </div>
      <h3>No workflow yet</h3>
      <p>Type a prompt in the chat panel to generate a workflow</p>
      <div className="wf-canvas-empty-hint">
        <MousePointerClick size={13} strokeWidth={1.8} />
        <span>Your workflow will appear here as an interactive node graph</span>
      </div>
    </div>
  );
}

// ─── Component ───────────────────────────────────────────────────────────────

const WorkflowCanvas = ({ draft, selectedNodeId, onSelectNode }: WorkflowCanvasProps) => {
  const initialNodes = useMemo<Node<WorkflowNodeData>[]>(() => {
    if (!draft) return [];
    return draft.nodes.map((n) => mapToRFNode(n, selectedNodeId));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const initialEdges = useMemo<Edge[]>(() => {
    if (!draft) return [];
    return draft.edges.map(mapToRFEdge);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Sync when draft changes externally
  useEffect(() => {
    if (!draft) {
      setNodes([]);
      setEdges([]);
      return;
    }
    setNodes(draft.nodes.map((n) => mapToRFNode(n, selectedNodeId)));
    setEdges(draft.edges.map(mapToRFEdge));
  }, [draft, selectedNodeId, setNodes, setEdges]);

  const onConnect = useCallback(
    (connection: Connection) => setEdges((eds) => addEdge(connection, eds)),
    [setEdges]
  );

  const onNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      onSelectNode(node.id === selectedNodeId ? null : node.id);
    },
    [onSelectNode, selectedNodeId]
  );

  const onPaneClick = useCallback(() => {
    onSelectNode(null);
  }, [onSelectNode]);

  if (!draft) {
    return (
      <div className="wf-canvas-wrap">
        <CanvasEmptyState />
      </div>
    );
  }

  return (
    <div className="wf-canvas-wrap">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={onNodeClick}
        onPaneClick={onPaneClick}
        nodeTypes={NODE_TYPES}
        fitView
        fitViewOptions={{ padding: 0.2, maxZoom: 1.2 }}
        minZoom={0.3}
        maxZoom={2}
        proOptions={{ hideAttribution: true }}
        style={{ background: "transparent" }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={28}
          size={1}
          color="rgba(255,255,255,0.05)"
        />
        <Controls
          className="wf-canvas-controls"
          showInteractive={false}
        />
        <MiniMap
          className="wf-canvas-minimap"
          nodeColor={(node) => {
            const data = node.data as WorkflowNodeData;
            const statusColors: Record<string, string> = {
              idle: "#1E2935",
              running: "#00CACC",
              success: "#22C55E",
              error: "#EF4444",
              waiting: "#F59E0B",
            };
            return statusColors[data?.status as string] ?? "#1E2935";
          }}
          maskColor="rgba(5,8,10,0.6)"
          style={{ background: "rgba(5,8,10,0.75)", borderColor: "rgba(255,255,255,0.06)" }}
        />
      </ReactFlow>
    </div>
  );
};

export default WorkflowCanvas;
