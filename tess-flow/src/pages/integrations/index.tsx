import { useState } from "react";
import { Plug, Search, X, Shield, AlertTriangle } from "lucide-react";
import { IntegrationType } from "../../types";
import { MOCK_INTEGRATIONS } from "../../data/mockData";
import PageShell from "../../shared/PageShell";
import StatusBadge from "../../shared/StatusBadge";
import EmptyState from "../../shared/EmptyState";

const IntegrationsPage = () => {
  const [activeTab, setActiveTab] = useState<"catalog" | "connected" | "channels">("catalog");
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<IntegrationType | "all">("all");

  const connected = MOCK_INTEGRATIONS.filter((i) => i.status === "connected");
  const channels = MOCK_INTEGRATIONS.filter((i) => i.type === "channel");
  
  const catalog = MOCK_INTEGRATIONS.filter((i) => {
    const matchesSearch = !search || i.name.toLowerCase().includes(search.toLowerCase());
    const matchesType = typeFilter === "all" || i.type === typeFilter;
    return matchesSearch && matchesType;
  });

  const getRiskColor = (level: "low" | "medium" | "high") => {
    if (level === "low") return "text-green-400";
    if (level === "medium") return "text-amber-400";
    return "text-red-400";
  };

  return (
    <PageShell>
      {/* Tabs */}
      <div className="tf-tabs">
        <button
          type="button"
          className={`tf-tab ${activeTab === "catalog" ? "active" : ""}`}
          onClick={() => setActiveTab("catalog")}
        >
          Catalog
        </button>
        <button
          type="button"
          className={`tf-tab ${activeTab === "connected" ? "active" : ""}`}
          onClick={() => setActiveTab("connected")}
        >
          Connected ({connected.length})
        </button>
        <button
          type="button"
          className={`tf-tab ${activeTab === "channels" ? "active" : ""}`}
          onClick={() => setActiveTab("channels")}
        >
          Channels & Accounts
        </button>
      </div>

      {/* Catalog Tab */}
      {activeTab === "catalog" && (
        <>
          <div className="tf-toolbar">
            <div className="tf-search-wrap">
              <Search size={14} className="tf-search-icon" />
              <input
                type="text"
                className="tf-search"
                placeholder="Search integrations..."
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
              {(["all", "channel", "productivity", "knowledge", "web3", "mcp"] as const).map((f) => (
                <button
                  key={f}
                  type="button"
                  className={`tf-filter-chip ${typeFilter === f ? "active" : ""}`}
                  onClick={() => setTypeFilter(f)}
                >
                  {f === "all" ? "All" : f.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div className="tf-integration-grid">
            {catalog.map((int) => (
              <div key={int.id} className="tf-integration-card">
                <div className="tf-integration-header">
                  <div className="tf-integration-icon-wrap">
                    <Plug size={20} strokeWidth={1.8} />
                  </div>
                  <StatusBadge variant={int.status} />
                </div>

                <h3 className="tf-integration-name">{int.name}</h3>
                <p className="tf-integration-desc">{int.description}</p>

                <div className="tf-integration-meta">
                  <span className="tf-integration-type">{int.type}</span>
                  <span className={`tf-integration-risk ${getRiskColor(int.riskLevel)}`}>
                    {int.riskLevel === "high" ? <AlertTriangle size={10} /> : <Shield size={10} />}
                    {int.riskLevel} risk
                  </span>
                </div>

                <button type="button" className="tf-btn secondary full">
                  {int.status === "connected" ? "Manage" : "Connect"}
                </button>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Connected Tab */}
      {activeTab === "connected" && (
        <>
          {connected.length === 0 ? (
            <EmptyState
              icon={<Plug size={32} strokeWidth={1.5} />}
              title="No connected integrations"
              description="Connect your first integration to enable agents to access external services."
              action={
                <button type="button" className="tf-btn primary" onClick={() => setActiveTab("catalog")}>
                  Browse Catalog
                </button>
              }
            />
          ) : (
            <div className="tf-integration-list">
              {connected.map((int) => (
                <div key={int.id} className="tf-integration-row">
                  <div className="tf-integration-row-left">
                    <div className="tf-integration-icon-wrap">
                      <Plug size={18} strokeWidth={1.8} />
                    </div>
                    <div>
                      <div className="tf-integration-row-name">{int.name}</div>
                      <div className="tf-integration-row-meta">
                        {int.connectedAgents} agents • Last sync {new Date(int.lastSync!).toLocaleTimeString()}
                      </div>
                    </div>
                  </div>

                  <div className="tf-integration-row-right">
                    <StatusBadge variant="connected" />
                    <button type="button" className="tf-btn ghost tiny">
                      Manage
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Channels Tab */}
      {activeTab === "channels" && (
        <div className="tf-integration-grid">
          {channels.map((ch) => (
            <div key={ch.id} className="tf-integration-card">
              <div className="tf-integration-header">
                <div className="tf-integration-icon-wrap">
                  <Plug size={20} strokeWidth={1.8} />
                </div>
                <StatusBadge variant={ch.status} />
              </div>

              <h3 className="tf-integration-name">{ch.name}</h3>
              <p className="tf-integration-desc">{ch.description}</p>

              {ch.status === "connected" && (
                <div className="tf-integration-scopes">
                  {ch.scopes.map((scope) => (
                    <span key={scope} className="tf-scope-tag">{scope}</span>
                  ))}
                </div>
              )}

              <button type="button" className="tf-btn secondary full">
                {ch.status === "connected" ? "Configure" : "Connect"}
              </button>
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
};

export default IntegrationsPage;
