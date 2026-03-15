/**
 * LeftDock — Primary navigation sidebar.
 * Clean, minimal design with smooth open/close transitions.
 * All text elements fade via opacity+max-width (no layout jumps).
 */
import {
  MessageSquare,
  Newspaper,
  Compass,
  ListTodo,
  Store,
  Plug,
  Wallet,
  Clock,
  Brain,
  Inbox,
  Settings,
  PanelLeftClose,
  PanelLeftOpen,
  Workflow,
  TrendingUp,
} from "lucide-react";
import { useState } from "react";
import { AppView } from "../types";
import { getBadgeCounts } from "../data/mockData";

interface LeftDockProps {
  activeView: AppView;
  onNavigate: (view: AppView) => void;
}

interface NavItem {
  id: AppView;
  label: string;
  icon: typeof MessageSquare;
  badgeKey?: "tasks" | "wallet" | "inbox";
}

const TOP_NAV: NavItem[] = [
  { id: "chat",         label: "Chat",               icon: MessageSquare },
  { id: "studio",       label: "Workflow Studio",    icon: Workflow },
  { id: "news",         label: "News Scout",         icon: Newspaper },
  { id: "tasks",        label: "Tasks",              icon: ListTodo,      badgeKey: "tasks" },
  { id: "store",        label: "Agent Store",        icon: Store },
  { id: "integrations", label: "Integrations",       icon: Plug },
  { id: "wallet",       label: "Wallet / Approvals", icon: Wallet,        badgeKey: "wallet" },
  { id: "history",      label: "History",            icon: Clock },
  { id: "memory",       label: "Memory",             icon: Brain },
  { id: "inbox",        label: "Inbox",              icon: Inbox,          badgeKey: "inbox" },
  { id: "portfolio",    label: "Portfolio Agent",    icon: TrendingUp },
];

const LeftDock = ({ activeView, onNavigate }: LeftDockProps) => {
  const [expanded, setExpanded] = useState(false);
  const badges = getBadgeCounts();

  return (
    <aside className={`left-dock ${expanded ? "expanded" : "collapsed"}`} aria-label="Navigation">

      {/* ── Brand ── */}
      <div className="ld-brand">
        <div className="ld-logo-wrap">
          <img src="/tesseris-logo.png" alt="TessFlow" className="ld-logo" />
        </div>
        <span className="ld-brand-name">TessFlow</span>
      </div>

      {/* ── Nav Items ── */}
      <nav className="ld-nav">
        {TOP_NAV.map((item) => {
          const Icon = item.icon;
          const isActive = activeView === item.id;
          const badgeCount = item.badgeKey ? badges[item.badgeKey] : 0;

          return (
            <button
              key={item.id}
              type="button"
              className={`ld-nav-item ${isActive ? "active" : ""}`}
              onClick={() => onNavigate(item.id)}
              title={!expanded ? item.label : undefined}
            >
              <span className="ld-nav-icon-wrap">
                <Icon size={18} strokeWidth={1.7} />
                {badgeCount > 0 && !expanded && (
                  <span className="ld-badge-dot" />
                )}
              </span>
              <span className="ld-nav-label">{item.label}</span>
              {badgeCount > 0 && (
                <span className="ld-badge-count">{badgeCount}</span>
              )}
              {!expanded && <span className="ld-tooltip">{item.label}</span>}
            </button>
          );
        })}
      </nav>

      {/* ── Spacer ── */}
      <div className="ld-spacer" />

      {/* ── Bottom section — Settings + Collapse ── */}
      <div className="ld-bottom">
        <button
          type="button"
          className={`ld-nav-item ${activeView === "explorer" ? "active" : ""}`}
          onClick={() => onNavigate("explorer")}
          title={!expanded ? "Explorer" : undefined}
        >
          <span className="ld-nav-icon-wrap">
            <Compass size={18} strokeWidth={1.7} />
          </span>
          <span className="ld-nav-label">Explorer</span>
          {!expanded && <span className="ld-tooltip">Explorer</span>}
        </button>

        <button
          type="button"
          className={`ld-nav-item ${activeView === "settings" ? "active" : ""}`}
          onClick={() => onNavigate("settings")}
          title={!expanded ? "Settings" : undefined}
        >
          <span className="ld-nav-icon-wrap">
            <Settings size={18} strokeWidth={1.7} />
          </span>
          <span className="ld-nav-label">Settings</span>
          {!expanded && <span className="ld-tooltip">Settings</span>}
        </button>

        <button
          type="button"
          className="ld-collapse-toggle"
          onClick={() => setExpanded(!expanded)}
          title={expanded ? "Collapse sidebar" : "Expand sidebar"}
        >
          <span className="ld-nav-icon-wrap">
            {expanded ? (
              <PanelLeftClose size={18} strokeWidth={1.7} />
            ) : (
              <PanelLeftOpen size={18} strokeWidth={1.7} />
            )}
          </span>
        </button>
      </div>
    </aside>
  );
};

export default LeftDock;
