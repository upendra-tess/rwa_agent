import { Wallet, Bell } from "lucide-react";
import { useState } from "react";
import { AppView } from "../types";
import { getBadgeCounts } from "../data/mockData";

interface AppHeaderProps {
  activeView: AppView;
}

const VIEW_TITLES: Record<AppView, { title: string; subtitle: string }> = {
  chat: { title: "Chat", subtitle: "Intent-first AI orchestration" },
  studio: { title: "Workflow Studio", subtitle: "Chat-driven visual workflow builder" },
  portfolio: { title: "Portfolio Management Agent", subtitle: "On-chain intelligence powered by LangGraph + Ethereum" },
  news: { title: "News Scout", subtitle: "Daily AI + Web3 signal feed curated for relevance and quality" },
  explorer: { title: "Explorer", subtitle: "Browse explorer.tesseris.org inside TessFlow" },
  store: { title: "Agent Store", subtitle: "Discover, compare, and add agents" },
  tasks: { title: "Tasks", subtitle: "Live, queued, and scheduled operations" },
  integrations: { title: "Integrations", subtitle: "Connect tools, channels, and data" },
  wallet: { title: "Wallet & Approvals", subtitle: "Control center for trust and spending" },
  history: { title: "History", subtitle: "Archive of past runs and artifacts" },
  memory: { title: "Memory", subtitle: "Reusable context and preferences" },
  inbox: { title: "Inbox", subtitle: "Events requiring your attention" },
  settings: { title: "Settings", subtitle: "Account, security, and preferences" },
};

const AppHeader = ({ activeView }: AppHeaderProps) => {
  const [isWalletConnected, setIsWalletConnected] = useState(false);
  const badges = getBadgeCounts();
  const { title, subtitle } = VIEW_TITLES[activeView];

  return (
    <header className="app-header">
      <div className="app-header-left">
        <div className="app-header-titles">
          <h1 className="app-header-title">{title}</h1>
          <span className="app-header-subtitle">{subtitle}</span>
        </div>
      </div>

      <div className="app-header-right">
        <button type="button" className="app-header-icon-btn" aria-label="Notifications" title="Notifications">
          <Bell size={16} strokeWidth={2} />
          {badges.inbox > 0 && <span className="app-header-notif-dot" />}
        </button>

        <button
          type="button"
          className={`app-header-wallet-btn ${isWalletConnected ? "connected" : ""}`}
          onClick={() => setIsWalletConnected((prev) => !prev)}
        >
          <span className="app-header-wallet-icon">
            <Wallet size={14} strokeWidth={2} />
          </span>
          <span className="app-header-wallet-text">
            {isWalletConnected ? "0x7A3...91F2" : "Connect"}
          </span>
          <span className={`app-header-wallet-dot ${isWalletConnected ? "connected" : ""}`} />
        </button>
      </div>
    </header>
  );
};

export default AppHeader;
