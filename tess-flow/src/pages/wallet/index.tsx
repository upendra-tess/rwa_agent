import { useState } from "react";
import { CheckCircle2, Clock, Receipt, Plus } from "lucide-react";
import { MOCK_APPROVALS, MOCK_WALLETS, MOCK_RECEIPTS } from "../../data/mockData";
import PageShell from "../../shared/PageShell";
import StatusBadge from "../../shared/StatusBadge";
import AgentIcon from "../../shared/AgentIcon";
import EmptyState from "../../shared/EmptyState";

const WalletPage = () => {
  const [activeTab, setActiveTab] = useState<"approvals" | "wallets" | "receipts">("approvals");

  const pending = MOCK_APPROVALS.filter((a) => a.status === "pending");

  return (
    <PageShell>
      {/* Tabs */}
      <div className="tf-tabs">
        <button
          type="button"
          className={`tf-tab ${activeTab === "approvals" ? "active" : ""}`}
          onClick={() => setActiveTab("approvals")}
        >
          Approvals ({pending.length})
        </button>
        <button
          type="button"
          className={`tf-tab ${activeTab === "wallets" ? "active" : ""}`}
          onClick={() => setActiveTab("wallets")}
        >
          Wallets
        </button>
        <button
          type="button"
          className={`tf-tab ${activeTab === "receipts" ? "active" : ""}`}
          onClick={() => setActiveTab("receipts")}
        >
          Receipts
        </button>
      </div>

      {/* Approvals Tab */}
      {activeTab === "approvals" && (
        <>
          {pending.length === 0 ? (
            <EmptyState
              icon={<CheckCircle2 size={32} strokeWidth={1.5} />}
              title="No pending approvals"
              description="All caught up! No agents are waiting for your approval."
            />
          ) : (
            <div className="tf-approval-list">
              {MOCK_APPROVALS.map((appr) => (
                <div key={appr.id} className={`tf-approval-card ${appr.status === "expired" ? "expired" : ""}`}>
                  <div className="tf-approval-header">
                    <div className="tf-approval-agent">
                      <div className="tf-approval-agent-icon">
                        <AgentIcon name={appr.agentIconName} size={16} />
                      </div>
                      <div>
                        <div className="tf-approval-agent-name">{appr.agentName}</div>
                        <div className="tf-approval-task">{appr.taskName}</div>
                      </div>
                    </div>
                    <StatusBadge variant={appr.riskLevel} />
                  </div>

                  <div className="tf-approval-action">{appr.requestedAction}</div>

                  {appr.amount && (
                    <div className="tf-approval-amount">{appr.amount}</div>
                  )}

                  <div className="tf-approval-footer">
                    <div className="tf-approval-expiry">
                      <Clock size={12} strokeWidth={2} />
                      Expires {new Date(appr.expiresAt).toLocaleString()}
                    </div>

                    {appr.status === "pending" && (
                      <div className="tf-approval-actions">
                        <button type="button" className="tf-btn ghost tiny">
                          Reject
                        </button>
                        <button type="button" className="tf-btn primary tiny">
                          <CheckCircle2 size={12} strokeWidth={2} />
                          Approve
                        </button>
                      </div>
                    )}

                    {appr.status === "expired" && (
                      <StatusBadge variant="error" label="Expired" />
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Wallets Tab */}
      {activeTab === "wallets" && (
        <>
          <div className="tf-wallet-grid">
            {MOCK_WALLETS.map((w) => (
              <div key={w.id} className="tf-wallet-card">
                <div className="tf-wallet-header">
                  <div className="tf-wallet-name">{w.name}</div>
                  {w.isDefault && <span className="tf-wallet-default-badge">Default</span>}
                </div>

                <div className="tf-wallet-address">{w.address}</div>
                <div className="tf-wallet-network">{w.network}</div>

                <div className="tf-wallet-balance">{w.balance}</div>

                <div className="tf-wallet-footer">
                  <StatusBadge variant={w.status} />
                  <button type="button" className="tf-btn ghost tiny">
                    Manage
                  </button>
                </div>
              </div>
            ))}

            <button type="button" className="tf-wallet-card tf-wallet-add">
              <Plus size={24} strokeWidth={1.8} />
              <div className="tf-wallet-add-label">Connect Wallet</div>
            </button>
          </div>
        </>
      )}

      {/* Receipts Tab */}
      {activeTab === "receipts" && (
        <div className="tf-receipt-list">
          {MOCK_RECEIPTS.map((rcpt) => (
            <div key={rcpt.id} className="tf-receipt-row">
              <div className="tf-receipt-left">
                <Receipt size={16} strokeWidth={1.8} />
                <div>
                  <div className="tf-receipt-task">{rcpt.taskName}</div>
                  <div className="tf-receipt-agent">{rcpt.agentName}</div>
                </div>
              </div>

              <div className="tf-receipt-right">
                <div className="tf-receipt-amount">{rcpt.amount}</div>
                <StatusBadge variant={rcpt.status} />
                <div className="tf-receipt-date">{new Date(rcpt.date).toLocaleDateString()}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
};

export default WalletPage;
