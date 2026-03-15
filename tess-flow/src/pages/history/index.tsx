import { useState } from "react";
import { Clock, Search, X, Download } from "lucide-react";
import { MOCK_HISTORY } from "../../data/mockData";
import PageShell from "../../shared/PageShell";
import StatusBadge from "../../shared/StatusBadge";
import EmptyState from "../../shared/EmptyState";

const HistoryPage = () => {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<"all" | "run" | "artifact" | "conversation">("all");

  const filtered = MOCK_HISTORY.filter((h) => {
    const matchesSearch = !search || h.title.toLowerCase().includes(search.toLowerCase());
    const matchesType = typeFilter === "all" || h.type === typeFilter;
    return matchesSearch && matchesType;
  });

  return (
    <PageShell>
      {/* Toolbar */}
      <div className="tf-toolbar">
        <div className="tf-search-wrap">
          <Search size={14} className="tf-search-icon" />
          <input
            type="text"
            className="tf-search"
            placeholder="Search history..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          {search && (
            <button type="button" className="tf-search-clear" onClick={() => setSearch("")} aria-label="Clear search">
              <X size={12} strokeWidth={2} />
            </button>
          )}
        </div>

        <div className="tf-filter-chips">
          {(["all", "run", "artifact", "conversation"] as const).map((f) => (
            <button
              key={f}
              type="button"
              className={`tf-filter-chip ${typeFilter === f ? "active" : ""}`}
              onClick={() => setTypeFilter(f)}
            >
              {f === "all" ? "All" : f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* History List */}
      {filtered.length === 0 ? (
        <EmptyState
          icon={<Clock size={32} strokeWidth={1.5} />}
          title="No history found"
          description="Try adjusting your filters or search query."
          action={
            <button type="button" className="tf-btn secondary" onClick={() => { setTypeFilter("all"); setSearch(""); }}>
              Clear Filters
            </button>
          }
        />
      ) : (
        <div className="tf-history-list">
          {filtered.map((item) => (
            <div key={item.id} className="tf-history-card">
              <div className="tf-history-header">
                <div className="tf-history-left">
                  <h3 className="tf-history-title">{item.title}</h3>
                  <div className="tf-history-meta">
                    {item.agentNames.join(", ")} • {new Date(item.date).toLocaleDateString()}
                  </div>
                </div>
                <StatusBadge variant={item.status} />
              </div>

              <div className="tf-history-details">
                <span className="tf-history-detail">Type: {item.type}</span>
                {item.integrations.length > 0 && (
                  <span className="tf-history-detail">
                    {item.integrations.slice(0, 2).join(", ")}
                    {item.integrations.length > 2 && ` +${item.integrations.length - 2}`}
                  </span>
                )}
                {item.artifactCount > 0 && (
                  <span className="tf-history-detail">{item.artifactCount} artifacts</span>
                )}
                {item.durationMs > 0 && (
                  <span className="tf-history-detail">{(item.durationMs / 1000).toFixed(1)}s</span>
                )}
              </div>

              <div className="tf-history-actions">
                <button type="button" className="tf-btn ghost tiny">
                  View
                </button>
                {item.type === "run" && (
                  <button type="button" className="tf-btn ghost tiny">
                    Clone
                  </button>
                )}
                <button type="button" className="tf-btn ghost tiny">
                  <Download size={12} strokeWidth={2} />
                  Export
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
};

export default HistoryPage;
