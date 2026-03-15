import { useState } from "react";
import { Brain, Search, X, Trash2, Edit } from "lucide-react";
import { MOCK_MEMORY } from "../../data/mockData";
import PageShell from "../../shared/PageShell";
import EmptyState from "../../shared/EmptyState";

const MemoryPage = () => {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<"all" | "preference" | "knowledge" | "entity" | "source" | "privacy">("all");

  const filtered = MOCK_MEMORY.filter((m) => {
    const matchesSearch = !search || m.name.toLowerCase().includes(search.toLowerCase());
    const matchesType = typeFilter === "all" || m.type === typeFilter;
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
            placeholder="Search memory..."
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
          {(["all", "preference", "knowledge", "entity", "source", "privacy"] as const).map((f) => (
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

      {/* Memory List */}
      {filtered.length === 0 ? (
        <EmptyState
          icon={<Brain size={32} strokeWidth={1.5} />}
          title="No memory items found"
          description="Try adjusting your filters or search query."
          action={
            <button type="button" className="tf-btn secondary" onClick={() => { setTypeFilter("all"); setSearch(""); }}>
              Clear Filters
            </button>
          }
        />
      ) : (
        <div className="tf-memory-list">
          {filtered.map((mem) => (
            <div key={mem.id} className="tf-memory-card">
              <div className="tf-memory-header">
                <div className="tf-memory-left">
                  <h3 className="tf-memory-name">{mem.name}</h3>
                  <div className="tf-memory-category">{mem.category}</div>
                </div>
                <span className="tf-memory-type-badge">{mem.type}</span>
              </div>

              <p className="tf-memory-desc">{mem.description}</p>

              <div className="tf-memory-footer">
                <div className="tf-memory-updated">
                  Updated {new Date(mem.lastUpdated).toLocaleDateString()}
                </div>
                <div className="tf-memory-actions">
                  <button type="button" className="tf-btn ghost tiny">
                    <Edit size={12} strokeWidth={2} />
                    Edit
                  </button>
                  <button type="button" className="tf-btn ghost tiny">
                    <Trash2 size={12} strokeWidth={2} />
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
};

export default MemoryPage;
