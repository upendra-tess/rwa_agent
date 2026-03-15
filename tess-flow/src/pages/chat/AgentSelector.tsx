import { X, Search } from "lucide-react";
import { Agent } from "../../types";
import AgentIcon from "../../shared/AgentIcon";

interface AgentSelectorProps {
  agents: Agent[];
  installedAgentIds: string[];
  onSelect: (agent: Agent) => void;
  onClose: () => void;
}

import { useState } from "react";

const AgentSelector = ({ agents, installedAgentIds, onSelect, onClose }: AgentSelectorProps) => {
  const [search, setSearch] = useState("");

  const installed = agents.filter((a) => installedAgentIds.includes(a.id));
  const other = agents.filter((a) => !installedAgentIds.includes(a.id));

  const filterFn = (a: Agent) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return a.name.toLowerCase().includes(q) || a.description.toLowerCase().includes(q);
  };

  const filteredInstalled = installed.filter(filterFn);
  const filteredOther = other.filter(filterFn);

  return (
    <div className="agent-selector-overlay" onClick={onClose}>
      <div className="agent-selector" onClick={(e) => e.stopPropagation()}>
        <div className="agent-selector-header">
          <h2>Choose an Agent</h2>
          <button type="button" className="agent-selector-close" onClick={onClose}>
            <X size={16} strokeWidth={2} />
          </button>
        </div>

        <div className="agent-selector-search-wrap">
          <Search size={13} strokeWidth={2} className="agent-selector-search-icon" />
          <input
            type="text"
            className="agent-selector-search"
            placeholder="Search agents…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            autoFocus
          />
        </div>

        <div className="agent-selector-list">
          {filteredInstalled.length > 0 && (
            <div className="agent-selector-group">
              <p className="agent-selector-group-label">Installed</p>
              {filteredInstalled.map((agent) => (
                <button
                  key={agent.id}
                  type="button"
                  className="agent-selector-item"
                  onClick={() => onSelect(agent)}
                >
                  <div className="agent-selector-item-icon">
                    <AgentIcon name={agent.iconName} size={16} />
                  </div>
                  <div className="agent-selector-item-info">
                    <span className="agent-selector-item-name">{agent.name}</span>
                    <span className="agent-selector-item-desc">{agent.description}</span>
                  </div>
                </button>
              ))}
            </div>
          )}

          {filteredOther.length > 0 && (
            <div className="agent-selector-group">
              <p className="agent-selector-group-label">Available</p>
              {filteredOther.map((agent) => (
                <button
                  key={agent.id}
                  type="button"
                  className="agent-selector-item"
                  onClick={() => onSelect(agent)}
                >
                  <div className="agent-selector-item-icon">
                    <AgentIcon name={agent.iconName} size={16} />
                  </div>
                  <div className="agent-selector-item-info">
                    <span className="agent-selector-item-name">{agent.name}</span>
                    <span className="agent-selector-item-desc">{agent.description}</span>
                  </div>
                </button>
              ))}
            </div>
          )}

          {filteredInstalled.length === 0 && filteredOther.length === 0 && (
            <div className="agent-selector-empty">
              <p>No agents found</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default AgentSelector;
