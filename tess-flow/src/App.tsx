/**
 * App.tsx — Root application entry.
 *
 * Architecture:
 *   app-shell
 *   ├── LeftDock          (persistent navigation sidebar)
 *   └── app-main
 *       ├── AppHeader     (universal page header shown on all views)
 *       ├── app-content
 *       │   └── <Page />  (one of the 9 product surfaces)
 *       └── ActivityBar   (thin bottom bar with status & quick actions)
 *
 * Folder structure:
 *   src/layout/      — LeftDock, AppHeader, ActivityBar
 *   src/shared/      — reusable components (AgentIcon, StatusBadge, etc.)
 *   src/pages/chat/  — Chat page + private sub-components
 *   src/pages/store/ — Agent Store page + private sub-components
 *   src/pages/tasks/ — Tasks page
 *   ... (one folder per product surface)
 */
import { useState } from "react";
import { Agent, AppView } from "./types";

// Layout
import LeftDock from "./layout/LeftDock";
import AppHeader from "./layout/AppHeader";
import ActivityBar from "./layout/ActivityBar";

// Pages (each folder owns its page + private sub-components)
import ChatPage from "./pages/chat/ChatPage";
import NewsPage from "./pages/news/index";
import ExplorerPage from "./pages/explorer/index";
import AgentRegistry from "./pages/store/AgentRegistry";
import TasksPage from "./pages/tasks/index";
import IntegrationsPage from "./pages/integrations/index";
import WalletPage from "./pages/wallet/index";
import HistoryPage from "./pages/history/index";
import MemoryPage from "./pages/memory/index";
import InboxPage from "./pages/inbox/index";
import SettingsPage from "./pages/settings/index";
import WorkflowStudioPage from "./pages/studio/WorkflowStudioPage";
import PortfolioPage from "./pages/portfolio/index";
const App = () => {
  const [view, setView] = useState<AppView>("chat");
  const [installed, setInstalled] = useState<Agent[]>([]);

  // Track mouse coordinates for the background glow
  const handleMouseMove = (e: React.MouseEvent) => {
    document.documentElement.style.setProperty('--mouse-x', `${e.clientX}px`);
    document.documentElement.style.setProperty('--mouse-y', `${e.clientY}px`);
  };

  const install = (agent: Agent) => {
    setInstalled((prev) => (prev.some((a) => a.id === agent.id) ? prev : [...prev, agent]));
  };

  return (
    <div className="app-shell" onMouseMove={handleMouseMove}>
      <div className="interactive-grid" />
      <LeftDock activeView={view} onNavigate={setView} />

      <main className="app-main">
        <AppHeader activeView={view} />

        <div className="app-content">
          {view === "chat" && (
            <ChatPage installedAgents={installed} onInstallAgent={install} />
          )}
          {view === "news" && <NewsPage />}
          {view === "explorer" && <ExplorerPage />}
          {view === "store" && (
            <AgentRegistry
              installedIds={installed.map((a) => a.id)}
              onInstall={(agent) => {
                install(agent);
                setView("chat");
              }}
              onOpen={() => setView("chat")}
            />
          )}
          {view === "tasks"        && <TasksPage />}
          {view === "integrations" && <IntegrationsPage />}
          {view === "wallet"       && <WalletPage />}
          {view === "history"      && <HistoryPage />}
          {view === "memory"       && <MemoryPage />}
          {view === "inbox"        && <InboxPage />}
          {view === "settings"     && <SettingsPage />}
          {view === "studio"       && <WorkflowStudioPage />}
          {view === "portfolio"    && <PortfolioPage />}
        </div>

        <ActivityBar
          onNavigateToWallet={() => setView("wallet")}
          onNavigateToIntegrations={() => setView("integrations")}
        />
      </main>
    </div>
  );
};

export default App;
