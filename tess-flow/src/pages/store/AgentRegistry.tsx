import { useEffect, useMemo, useRef, useState } from "react";
import {
  Search, Star, Download, ChevronRight, X,
  ShieldCheck, Users, Zap, BadgeCheck, Coins, ArrowLeftRight, SlidersHorizontal,
  type LucideIcon,
} from "lucide-react";
import { AGENT_CATALOG } from "../../data/catalog";
import { Agent, AgentCategory, AgentPublisher } from "../../types";
import AgentIcon from "../../shared/AgentIcon";

interface AgentRegistryProps {
  installedIds: string[];
  onInstall: (agent: Agent) => void;
  onOpen: (agentId: string) => void;
}

const CATEGORIES: AgentCategory[] = [
  "Data & Analytics", "Finance", "Productivity",
  "Developer Tools", "Research", "Communication", "Security",
];

const TESSERIS_LOGO_SRC = "/tesseris-logo.png";

type ActiveFilterChip = { key: "publisher" | "category"; label: string; clear: () => void };

interface StatusBadgeConfig {
  key: keyof Agent["badges"];
  label: string;
  tone: "verified" | "tx" | "token";
  titleOn: string;
  titleOff: string;
  icon: LucideIcon;
}

const STATUS_BADGES: StatusBadgeConfig[] = [
  {
    key: "verified",
    label: "Verified",
    tone: "verified",
    titleOn: "Agent Capability Verified",
    titleOff: "Agent Capability Not Verified",
    icon: BadgeCheck,
  },
  {
    key: "txEnabled",
    label: "Tx",
    tone: "tx",
    titleOn: "Agentic Transactions Enabled",
    titleOff: "Agentic Transactions Not Enabled",
    icon: ArrowLeftRight,
  },
  {
    key: "tokenListed",
    label: "Token",
    tone: "token",
    titleOn: "Agent Token Listed",
    titleOff: "Agent Token Not Listed",
    icon: Coins,
  },
];

const PublisherMeta = ({ agent }: { agent: Agent }) => {
  const isTesseris = agent.publisher === "Tesseris";
  const publisherName = isTesseris ? "Tesseris" : agent.author;

  return (
    <span className={`publisher-meta ${isTesseris ? "tesseris" : "community"}`}>
      {isTesseris ? (
        <img
          src={TESSERIS_LOGO_SRC}
          alt=""
          className="publisher-meta-logo"
          aria-hidden="true"
        />
      ) : (
        <Users size={11} strokeWidth={1.9} />
      )}
      <span className="publisher-meta-copy">
        Built by <strong>{publisherName}</strong>
      </span>
    </span>
  );
};

const StatusIndicators = ({
  badges,
  className = "",
}: {
  badges: Agent["badges"];
  className?: string;
}) => (
  <div className={["status-indicators", className].filter(Boolean).join(" ")}>
    {STATUS_BADGES.map(({ key, label, tone, titleOn, titleOff, icon: Icon }) => {
      const enabled = badges[key];
      const tooltipCopy = enabled ? titleOn : titleOff;

      return (
        <span
          key={key}
          className={`status-indicator status-${tone} ${enabled ? "is-on" : "is-off"}`}
          aria-label={`${label}: ${enabled ? "enabled" : "disabled"}`}
          tabIndex={0}
        >
          <Icon size={10} strokeWidth={2} />
          <span className="status-indicator-tooltip" role="tooltip">
            <span className="status-indicator-tooltip-copy">{tooltipCopy}</span>
          </span>
        </span>
      );
    })}
  </div>
);

const AgentRegistry = ({ installedIds, onInstall, onOpen }: AgentRegistryProps) => {
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<AgentCategory | "All">("All");
  const [selectedPublisher, setSelectedPublisher] = useState<AgentPublisher | "All">("All");
  const [detailAgent, setDetailAgent] = useState<Agent | null>(null);
  const [isFilterOpen, setIsFilterOpen] = useState(false);
  const filterPanelRef = useRef<HTMLDivElement | null>(null);

  const filtered = useMemo(() => {
    return AGENT_CATALOG.filter((agent) => {
      const q = search.toLowerCase().trim();
      const matchesSearch = !q ||
        agent.name.toLowerCase().includes(q) ||
        agent.description.toLowerCase().includes(q) ||
        agent.tags.some((t) => t.toLowerCase().includes(q));
      return matchesSearch
        && (selectedCategory  === "All" || agent.category  === selectedCategory)
        && (selectedPublisher === "All" || agent.publisher === selectedPublisher);
    });
  }, [search, selectedCategory, selectedPublisher]);

  const featured = AGENT_CATALOG.filter((a) => a.publisher === "Tesseris").slice(0, 3);
  const activeFilterCount = (selectedPublisher !== "All" ? 1 : 0) + (selectedCategory !== "All" ? 1 : 0);

  const formatRuns = (n: number) => n >= 1000 ? `${(n / 1000).toFixed(1)}k` : String(n);
  const clearFilters = () => {
    setSelectedCategory("All");
    setSelectedPublisher("All");
  };

  const activeFilters: ActiveFilterChip[] = [];

  if (selectedPublisher !== "All") {
    activeFilters.push({
      key: "publisher",
      label: selectedPublisher,
      clear: () => setSelectedPublisher("All"),
    });
  }

  if (selectedCategory !== "All") {
    activeFilters.push({
      key: "category",
      label: selectedCategory,
      clear: () => setSelectedCategory("All"),
    });
  }

  useEffect(() => {
    if (!isFilterOpen) return;

    const handlePointerDown = (event: MouseEvent) => {
      if (filterPanelRef.current && !filterPanelRef.current.contains(event.target as Node)) {
        setIsFilterOpen(false);
      }
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setIsFilterOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isFilterOpen]);

  const renderStars = (rating: number) =>
    Array.from({ length: 5 }, (_, i) => (
      <Star key={i} size={10} strokeWidth={0} fill={i < Math.floor(rating) ? "#F59E0B" : "#263241"} />
    ));

  return (
    <div className="registry-layout">
      <div className="registry-main">
        {/* Featured */}
        <section className="registry-featured">
          <h2 className="registry-section-title">
            <Zap size={12} strokeWidth={2} className="pub-icon-tesseris" /> Featured
          </h2>
          <div className="featured-grid">
            {featured.map((agent) => (
              <article key={agent.id} className="featured-card">
                <button type="button" className="featured-card-inner" onClick={() => setDetailAgent(agent)}>
                  <div className="featured-card-head">
                    <div className="featured-card-icon-name">
                      <div className="featured-card-icon"><AgentIcon name={agent.iconName} size={18} /></div>
                      <h3>{agent.name}</h3>
                    </div>
                    <StatusIndicators badges={agent.badges} className="featured-status-strip" />
                  </div>
                  <div className="featured-card-publisher">
                    <PublisherMeta agent={agent} />
                  </div>
                  <p className="featured-card-desc">{agent.description}</p>
                  <div className="featured-card-stats">
                    <div className="featured-card-meta-row">
                      <span className="registry-cat-tag">{agent.category}</span>
                    </div>
                    <div className="featured-card-footer">
                      <div className="agent-rating">
                        {renderStars(agent.rating)}
                        <span className="rating-score">{agent.rating}</span>
                      </div>
                      <span className="agent-runs">{formatRuns(agent.runCount)} runs</span>
                    </div>
                  </div>
                </button>

                <div className="featured-card-actions">
                  {installedIds.includes(agent.id) ? (
                    <button type="button" className="tf-btn secondary full" onClick={() => onOpen(agent.id)}>
                      Open <ChevronRight size={12} strokeWidth={2.5} />
                    </button>
                  ) : (
                    <button type="button" className="tf-btn accent full" onClick={() => onInstall(agent)}>
                      <Download size={12} strokeWidth={2} /> Add Agent
                    </button>
                  )}
                </div>
              </article>
            ))}
          </div>
        </section>

        {/* Grid */}
        <section>
          <div className="registry-section-header">
            <div className="registry-section-heading">
              <h2 className="registry-section-title">
                {selectedPublisher !== "All" ? selectedPublisher
                  : selectedCategory !== "All" ? selectedCategory
                  : "All Agents"}
              </h2>
            </div>

            <div className="registry-section-controls">
              <div className="registry-search-wrap">
                <Search size={14} strokeWidth={2} className="registry-search-icon" />
                <input
                  type="text"
                  className="registry-search"
                  placeholder="Search agents…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                {search && (
                  <button type="button" className="registry-search-clear" onClick={() => setSearch("")} aria-label="Clear">
                    <X size={12} strokeWidth={2} />
                  </button>
                )}
              </div>

              <div className="registry-filter-wrap" ref={filterPanelRef}>
                <button
                  type="button"
                  className={`registry-filter-trigger ${isFilterOpen ? "active" : ""}`}
                  onClick={() => setIsFilterOpen((prev) => !prev)}
                  aria-expanded={isFilterOpen ? "true" : "false"}
                  aria-haspopup="dialog"
                >
                  <SlidersHorizontal size={14} strokeWidth={2} />
                  Filters
                  {activeFilterCount > 0 && (
                    <span className="registry-filter-trigger-count">{activeFilterCount}</span>
                  )}
                </button>

                {isFilterOpen && (
                  <div className="registry-filter-panel" role="dialog" aria-label="Filter agents">
                    <div className="registry-filter-panel-section">
                      <p className="registry-filter-panel-label">Publisher</p>
                      <div className="registry-filter-options">
                        {(["All", "Tesseris", "Community"] as const).map((pub) => (
                          <button
                            key={pub}
                            type="button"
                            className={`registry-filter-pill ${selectedPublisher === pub ? "active" : ""}`}
                            onClick={() => setSelectedPublisher(pub)}
                          >
                            {pub === "Tesseris" && <ShieldCheck size={12} strokeWidth={2} className="pub-icon-tesseris" />}
                            {pub === "Community" && <Users size={12} strokeWidth={1.8} className="pub-icon-community" />}
                            {pub}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="registry-filter-panel-section">
                      <p className="registry-filter-panel-label">Category</p>
                      <div className="registry-filter-options">
                        {(["All", ...CATEGORIES] as const).map((cat) => (
                          <button
                            key={cat}
                            type="button"
                            className={`registry-filter-pill ${selectedCategory === cat ? "active" : ""}`}
                            onClick={() => setSelectedCategory(cat)}
                          >
                            {cat}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="registry-filter-panel-actions">
                      <button type="button" className="tf-btn ghost tiny" onClick={clearFilters}>
                        Clear
                      </button>
                      <button type="button" className="tf-btn secondary tiny" onClick={() => setIsFilterOpen(false)}>
                        Done
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </div>
          </div>

          {activeFilters.length > 0 && (
            <div className="registry-active-filters">
              {activeFilters.map((filter) => (
                <button key={filter.key} type="button" className="registry-active-filter" onClick={filter.clear}>
                  {filter.label}
                  <X size={10} strokeWidth={2} />
                </button>
              ))}
              <button type="button" className="registry-active-clear" onClick={clearFilters}>
                Clear all
              </button>
            </div>
          )}

          {filtered.length === 0 ? (
            <div className="registry-empty">
              <Search size={26} strokeWidth={1.5} />
              <p>No agents match your search.</p>
              <button type="button" className="tf-btn secondary" onClick={() => { setSearch(""); clearFilters(); }}>
                Clear filters
              </button>
            </div>
          ) : (
            <div className="agent-grid">
              {filtered.map((agent) => {
                const isInstalled = installedIds.includes(agent.id);
                return (
                  <article key={agent.id} className="agent-card">
                    <button type="button" className="agent-card-inner" onClick={() => setDetailAgent(agent)}>
                      <div className="ac-head">
                        {/* Row 1: icon + name */}
                        <div className="ac-icon-name">
                          <div className="agent-card-icon-wrap">
                            <AgentIcon name={agent.iconName} size={18} />
                          </div>
                          <h3 className="ac-name">{agent.name}</h3>
                        </div>
                        <StatusIndicators badges={agent.badges} className="card-status-strip" />
                      </div>

                      <div className="ac-publisher">
                        <PublisherMeta agent={agent} />
                      </div>

                      {/* Row 3–5: description (3 lines max) */}
                      <p className="ac-desc">{agent.description}</p>

                      {/* Row 6: capability pills */}
                      <div className="ac-caps">
                        {agent.capabilities.slice(0, 3).map((cap) => (
                          <span key={cap} className="agent-cap-tag">{cap}</span>
                        ))}
                      </div>

                      {/* Row 7: rating + runs */}
                      <div className="ac-footer">
                        <div className="agent-rating">
                          {renderStars(agent.rating)}
                          <span className="rating-score">{agent.rating}</span>
                        </div>
                        <span className="agent-runs">{formatRuns(agent.runCount)} runs</span>
                      </div>
                    </button>

                    {/* CTA */}
                    <div className="agent-card-actions">
                      {isInstalled ? (
                        <button type="button" className="tf-btn secondary agent-action-btn" onClick={() => onOpen(agent.id)}>
                          Open <ChevronRight size={12} strokeWidth={2.5} />
                        </button>
                      ) : (
                        <button type="button" className="tf-btn accent agent-action-btn" onClick={() => onInstall(agent)}>
                          <Download size={12} strokeWidth={2} /> Add Agent
                        </button>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>

      {/* ── Detail drawer ── */}
      {detailAgent && (
        <div className="detail-overlay" onClick={() => setDetailAgent(null)}>
          <aside className="detail-drawer" onClick={(e) => e.stopPropagation()}>
            <button type="button" className="detail-close" onClick={() => setDetailAgent(null)} aria-label="Close">
              <X size={15} strokeWidth={2} />
            </button>

            <div className="detail-header">
              <div className="detail-icon-wrap"><AgentIcon name={detailAgent.iconName} size={24} /></div>
              <div className="detail-header-copy">
                <div className="detail-title-row">
                  <h2>{detailAgent.name}</h2>
                  <StatusIndicators badges={detailAgent.badges} className="detail-status-strip" />
                </div>
                <div className="detail-meta">
                  <PublisherMeta agent={detailAgent} />
                  <span className="detail-meta-separator">·</span>
                  <span>v{detailAgent.version}</span>
                </div>
              </div>
            </div>

            <div className="detail-rating">
              {renderStars(detailAgent.rating)}
              <span className="rating-score">{detailAgent.rating}</span>
              <span className="muted">({detailAgent.reviewCount} reviews · {formatRuns(detailAgent.runCount)} runs)</span>
            </div>

            <span className="registry-cat-tag">{detailAgent.category}</span>
            <p className="detail-desc">{detailAgent.longDescription}</p>

            {detailAgent.publisher === "Community" && (
              <div className="community-notice">
                <Users size={13} strokeWidth={1.8} />
                <span>Community-built agent — review permissions before granting access to sensitive data.</span>
              </div>
            )}

            <div className="detail-caps">
              <h3>Capabilities</h3>
              <div className="detail-cap-list">
                {detailAgent.capabilities.map((cap) => (
                  <span key={cap} className="agent-cap-tag">{cap}</span>
                ))}
              </div>
            </div>

            <div className="detail-tags">
              <h3>Tags</h3>
              <div className="detail-cap-list">
                {detailAgent.tags.map((tag) => (
                  <span key={tag} className="agent-tag">{tag}</span>
                ))}
              </div>
            </div>

            <div className="detail-actions">
              {installedIds.includes(detailAgent.id) ? (
                <button type="button" className="tf-btn secondary full"
                  onClick={() => { onOpen(detailAgent.id); setDetailAgent(null); }}>
                  Open Workspace <ChevronRight size={13} strokeWidth={2.5} />
                </button>
              ) : (
                <button type="button" className="tf-btn accent full"
                  onClick={() => { onInstall(detailAgent); setDetailAgent(null); }}>
                  <Download size={13} strokeWidth={2} /> Add Agent
                </button>
              )}
            </div>
          </aside>
        </div>
      )}
    </div>
  );
};

export default AgentRegistry;
