import { useState } from "react";
import { Inbox, AlertCircle, CheckCircle2, Info, AlertTriangle, Zap, X } from "lucide-react";
import { MOCK_INBOX } from "../../data/mockData";
import PageShell from "../../shared/PageShell";
import EmptyState from "../../shared/EmptyState";

const InboxPage = () => {
  const [filter, setFilter] = useState<"all" | "unread" | "action_required">("all");

  const filtered = MOCK_INBOX.filter((i) => {
    if (filter === "unread") return !i.isRead;
    if (filter === "action_required") return i.category === "action_required";
    return true;
  });

  const unreadCount = MOCK_INBOX.filter((i) => !i.isRead).length;

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case "error": return <AlertCircle size={16} />;
      case "warning": return <AlertTriangle size={16} />;
      case "success": return <CheckCircle2 size={16} />;
      case "action": return <Zap size={16} />;
      default: return <Info size={16} />;
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "error": return "tf-inbox-error";
      case "warning": return "tf-inbox-warning";
      case "success": return "tf-inbox-success";
      case "action": return "tf-inbox-action";
      default: return "tf-inbox-info";
    }
  };

  return (
    <PageShell>
      {/* Filters */}
      <div className="tf-toolbar">
        <div className="tf-filter-chips">
          <button
            type="button"
            className={`tf-filter-chip ${filter === "all" ? "active" : ""}`}
            onClick={() => setFilter("all")}
          >
            All
          </button>
          <button
            type="button"
            className={`tf-filter-chip ${filter === "unread" ? "active" : ""}`}
            onClick={() => setFilter("unread")}
          >
            Unread ({unreadCount})
          </button>
          <button
            type="button"
            className={`tf-filter-chip ${filter === "action_required" ? "active" : ""}`}
            onClick={() => setFilter("action_required")}
          >
            Action Required
          </button>
        </div>
      </div>

      {/* Inbox List */}
      {filtered.length === 0 ? (
        <EmptyState
          icon={<Inbox size={32} strokeWidth={1.5} />}
          title="All caught up!"
          description="No items to show with the current filter."
        />
      ) : (
        <div className="tf-inbox-list">
          {filtered.map((item) => (
            <div
              key={item.id}
              className={`tf-inbox-item ${getSeverityColor(item.severity)} ${!item.isRead ? "unread" : ""}`}
            >
              <div className="tf-inbox-icon-wrap">
                {getSeverityIcon(item.severity)}
              </div>

              <div className="tf-inbox-content">
                <div className="tf-inbox-header">
                  <h3 className="tf-inbox-title">{item.title}</h3>
                  <div className="tf-inbox-time">
                    {new Date(item.timestamp).toLocaleTimeString()}
                  </div>
                </div>

                <p className="tf-inbox-desc">{item.description}</p>

                {item.primaryAction && (
                  <button type="button" className="tf-btn secondary tiny" style={{ marginTop: "8px" }}>
                    {item.primaryAction}
                  </button>
                )}
              </div>

              <button type="button" className="tf-inbox-dismiss" aria-label="Dismiss">
                <X size={14} strokeWidth={2} />
              </button>

              {!item.isRead && <div className="tf-inbox-unread-dot" />}
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
};

export default InboxPage;
