import { useState } from "react";
import { Zap, Play, Clock, CheckCircle2, XCircle, Search, X } from "lucide-react";
import { TaskStatus } from "../../types";
import { MOCK_TASKS } from "../../data/mockData";
import PageShell from "../../shared/PageShell";
import SummaryStatCard from "../../shared/SummaryStatCard";
import StatusBadge from "../../shared/StatusBadge";
import EmptyState from "../../shared/EmptyState";
import AgentIcon from "../../shared/AgentIcon";

type TaskFilter = "all" | TaskStatus;

const TasksPage = () => {
  const [filter, setFilter] = useState<TaskFilter>("all");
  const [search, setSearch] = useState("");

  const filtered = MOCK_TASKS.filter((t) => {
    const matchesFilter = filter === "all" || t.status === filter;
    const matchesSearch = !search || t.title.toLowerCase().includes(search.toLowerCase());
    return matchesFilter && matchesSearch;
  });

  const counts = {
    running: MOCK_TASKS.filter((t) => t.status === "running").length,
    waiting: MOCK_TASKS.filter((t) => t.status === "waiting").length,
    scheduled: MOCK_TASKS.filter((t) => t.status === "scheduled").length,
    completed: MOCK_TASKS.filter((t) => t.status === "completed").length,
    failed: MOCK_TASKS.filter((t) => t.status === "failed").length,
  };

  const formatTime = (iso: string) => {
    const date = new Date(iso);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "Just now";
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    return date.toLocaleDateString();
  };

  return (
    <PageShell>
      {/* Summary */}
      <div className="tf-stats-grid">
        <SummaryStatCard label="Running" value={counts.running} icon={<Play size={16} />} accent="teal" />
        <SummaryStatCard label="Waiting" value={counts.waiting} icon={<Clock size={16} />} accent="amber" />
        <SummaryStatCard label="Scheduled" value={counts.scheduled} icon={<Clock size={16} />} accent="blue" />
        <SummaryStatCard label="Completed" value={counts.completed} icon={<CheckCircle2 size={16} />} accent="green" />
        <SummaryStatCard label="Failed" value={counts.failed} icon={<XCircle size={16} />} accent="red" />
      </div>

      {/* Filters */}
      <div className="tf-toolbar">
        <div className="tf-search-wrap">
          <Search size={14} className="tf-search-icon" />
          <input
            type="text"
            className="tf-search"
            placeholder="Search tasks..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button type="button" className="tf-search-clear" onClick={() => setSearch("")}>
              <X size={12} strokeWidth={2} />
            </button>
          )}
        </div>

        <div className="tf-filter-chips">
          {(["all", "running", "waiting", "scheduled", "completed", "failed"] as const).map((f) => (
            <button
              key={f}
              type="button"
              className={`tf-filter-chip ${filter === f ? "active" : ""}`}
              onClick={() => setFilter(f)}
            >
              {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Task List */}
      {filtered.length === 0 ? (
        <EmptyState
          icon={<Zap size={32} strokeWidth={1.5} />}
          title="No tasks found"
          description="Try adjusting your filters or search query."
          action={
            <button type="button" className="tf-btn secondary" onClick={() => { setFilter("all"); setSearch(""); }}>
              Clear Filters
            </button>
          }
        />
      ) : (
        <div className="tf-task-list">
          {filtered.map((task) => (
            <div key={task.id} className="tf-task-card">
              <div className="tf-task-card-header">
                <div className="tf-task-card-agent">
                  <div className="tf-task-agent-icon">
                    <AgentIcon name={task.agentIconName} size={16} />
                  </div>
                  <div>
                    <div className="tf-task-agent-name">{task.agentName}</div>
                    <div className="tf-task-category">{task.category}</div>
                  </div>
                </div>
                <StatusBadge variant={task.status} />
              </div>

              <h3 className="tf-task-title">{task.title}</h3>
              <p className="tf-task-intent">{task.intentSummary}</p>

              {task.status === "running" && (
                <div className="tf-task-progress">
                  <div className="tf-task-progress-bar">
                    <div className="tf-task-progress-fill" style={{ width: `${task.progress}%` }} />
                  </div>
                  <span className="tf-task-progress-label">{task.progress}%</span>
                </div>
              )}

              <div className="tf-task-meta">
                <div className="tf-task-meta-row">
                  <span className="tf-task-meta-item">
                    {task.integrations.slice(0, 2).join(", ")}
                    {task.integrations.length > 2 && ` +${task.integrations.length - 2}`}
                  </span>
                  {task.costEstimate && (
                    <span className="tf-task-meta-item tf-task-cost">{task.costEstimate}</span>
                  )}
                  {task.approvalRequired && (
                    <span className="tf-task-meta-item tf-task-approval">Approval Required</span>
                  )}
                </div>
                <div className="tf-task-time">{formatTime(task.lastUpdated)}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
};

export default TasksPage;
