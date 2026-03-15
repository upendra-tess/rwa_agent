/**
 * PortfolioPage — Portfolio Management Agent
 *
 * Connects to the Flask backend (api.py / agent_graph.py) and exposes:
 *   • Natural-language chat powered by the LangGraph agent
 *   • Wallet connector (MetaMask → triggers SIGN_TX flow)
 *   • Real-time balance checks for both user & agent wallets
 *   • ETH transfer via MetaMask signing
 *   • New wallet creation
 *
 * UI follows TessFlow's glassmorphism design system (index.css).
 */

import { useState, useRef, useEffect, useCallback } from "react";
import {
  TrendingUp,
  Wallet,
  Send,
  RefreshCw,
  Copy,
  CheckCircle2,
  AlertTriangle,
  ArrowUpRight,
  ArrowDownLeft,
  Activity,
  PlusCircle,
  Bot,
  User,
  Loader2,
  Shield,
  Zap,
  BarChart3,
  DollarSign,
} from "lucide-react";
import "./portfolio.css";
import PageShell from "../../shared/PageShell";
import SummaryStatCard from "../../shared/SummaryStatCard";
import StatusBadge from "../../shared/StatusBadge";

// ─── Constants ────────────────────────────────────────────────────────────────

const API_BASE = "http://localhost:5000";

// ─── Extend Window to include MetaMask's ethereum provider ───────────────────
declare global {
  interface Window {
    ethereum?: {
      request: (args: { method: string; params?: unknown[] }) => Promise<unknown>;
      isMetaMask?: boolean;
    };
  }
}

// ─── Types ───────────────────────────────────────────────────────────────────

interface ChatMessage {
  id: string;
  role: "user" | "agent" | "system";
  text: string;
  timestamp: string;
  intent?: string;
  isLoading?: boolean;
}

interface WalletInfo {
  address: string;
  balance: number | null;
  network: string;
}

interface AgentInfo {
  address: string;
  balance: number | null;
}

interface PendingTx {
  amount_eth: number;
  amount_wei: string;
  from: string;
  to: string;
}

// ─── Helper ───────────────────────────────────────────────────────────────────

function shortAddr(addr: string): string {
  if (!addr || addr.length < 12) return addr;
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

function formatEth(val: number | null): string {
  if (val === null) return "—";
  return `${val.toFixed(4)} ETH`;
}

function now(): string {
  return new Date().toISOString();
}

function msgId(): string {
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

// ─── Quick-prompt chips shown below the input ─────────────────────────────────

const QUICK_PROMPTS = [
  "Check my wallet balance",
  "Check agent wallet balance",
  "Transfer 0.01 ETH to agent",
  "Create a new wallet",
  "I want 20% ROI in 1 year",
  "What is the market status?",
  "Tell me about ONDO",
  "Suggest trades for $500",
];

// ─── Market Intelligence Types ───────────────────────────────────────────────

interface MarketStatus {
  fear_greed: { value: number; label: string };
  gas: { slow_gwei: number; standard_gwei: number; fast_gwei: number };
  gainers_24h: { symbol: string; change_24h: number; price_usd: number }[];
  losers_24h:  { symbol: string; change_24h: number; price_usd: number }[];
  tokens_total: number;
  data_age_min: number;
}

interface TokenPick {
  symbol: string;
  name: string;
  current_price: number;
  composite_score: number;
  projected_roi_pct: number;
  rsi: number;
  macd_trend: string;
  bollinger_signal: string;
  risk_label: string;
  trust_score: number;
  recommendation: string;
  price_target_12m: number;
  apy_pct: number;
  tvl_usd: number;
}

interface PortfolioAlloc {
  symbol: string;
  alloc_pct: number;
  alloc_usd: number;
  buy_price: number;
  target_price: number;
  projected_roi: number;
  risk_label: string;
}

interface MarketReport {
  roi_target_pct: number;
  budget_usd: number;
  tokens_analyzed: number;
  hits_target_count: number;
  top_picks: TokenPick[];
  portfolio: {
    status: string;
    projected_roi_pct: number;
    hits_target: boolean;
    allocations: PortfolioAlloc[];
    message: string;
  };
  market_context: { fear_greed_value: number; fear_greed_label: string };
  warnings: string[];
}

interface RwaToken {
  id: string;
  symbol: string;
  name: string;
  price_usd: number;
  market_cap: number;
  tvl_usd: number;
  apy_pct: number;
  trust_score: number;
  trust_badge: string;
}

// ─── Main Component ───────────────────────────────────────────────────────────

const PortfolioPage = () => {
  // Chat state
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: msgId(),
      role: "system",
      text: "Portfolio Management Agent is ready. Connect your wallet and ask me anything about your on-chain assets.",
      timestamp: now(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);

  // Wallet state
  const [userWallet, setUserWallet] = useState<WalletInfo>({
    address: "",
    balance: null,
    network: "Ethereum Sepolia",
  });
  const [agentInfo, setAgentInfo] = useState<AgentInfo>({
    address: "",
    balance: null,
  });

  // Market Intelligence state
  const [marketStatus, setMarketStatus]     = useState<MarketStatus | null>(null);
  const [marketReport, setMarketReport]     = useState<MarketReport | null>(null);
  const [rwaTokens, setRwaTokens]           = useState<RwaToken[]>([]);
  const [isFetchingMarket, setIsFetchingMarket] = useState(false);
  const [roiInput, setRoiInput]             = useState("20");
  const [budgetInput, setBudgetInput]       = useState("1000");

  // UI state
  const [activeTab, setActiveTab] = useState<"chat" | "market" | "overview" | "transactions">("chat");
  const [isFetchingAgent, setIsFetchingAgent] = useState(false);
  const [isFetchingBalance, setIsFetchingBalance] = useState(false);
  const [pendingTx, setPendingTx] = useState<PendingTx | null>(null);
  const [txStatus, setTxStatus] = useState<"idle" | "signing" | "sent" | "error">("idle");
  const [txHash, setTxHash] = useState<string>("");
  const [copiedAddr, setCopiedAddr] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ── Auto-scroll ───────────────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isTyping]);

  // ── Fetch agent info on mount ─────────────────────────────────────────────
  useEffect(() => {
    fetchAgentInfo();
  }, []);

  // ── Fetch agent wallet info ───────────────────────────────────────────────
  const fetchAgentInfo = async () => {
    setIsFetchingAgent(true);
    try {
      const res = await fetch(`${API_BASE}/api/wallet/agent-info`);
      const data = await res.json();
      setAgentInfo({
        address: data.agent_address ?? "",
        balance: data.agent_balance ?? null,
      });
    } catch {
      // backend offline — show placeholder
      setAgentInfo({ address: "0x…(offline)", balance: null });
    } finally {
      setIsFetchingAgent(false);
    }
  };

  // ── Connect MetaMask wallet ───────────────────────────────────────────────
  const connectWallet = async () => {
    if (typeof window.ethereum === "undefined") {
      pushSystemMsg("MetaMask not detected. Please install the MetaMask extension.");
      return;
    }
    try {
      const accounts = (await window.ethereum.request({
        method: "eth_requestAccounts",
      })) as string[];
      const addr = accounts[0];
      setUserWallet((prev) => ({ ...prev, address: addr }));
      pushSystemMsg(`Wallet connected: ${shortAddr(addr)}`);
      fetchUserBalance(addr);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unknown error";
      pushSystemMsg(`Wallet connection failed: ${msg}`);
    }
  };

  // ── Fetch user's ETH balance via MetaMask ─────────────────────────────────
  const fetchUserBalance = async (addr: string) => {
    if (!addr || typeof window.ethereum === "undefined") return;
    setIsFetchingBalance(true);
    try {
      const hex = (await window.ethereum.request({
        method: "eth_getBalance",
        params: [addr, "latest"],
      })) as string;
      const wei = BigInt(hex);
      const eth = Number(wei) / 1e18;
      setUserWallet((prev) => ({ ...prev, balance: eth }));
    } catch {
      setUserWallet((prev) => ({ ...prev, balance: null }));
    } finally {
      setIsFetchingBalance(false);
    }
  };

  // ── Push a system notice into the chat ───────────────────────────────────
  const pushSystemMsg = useCallback((text: string) => {
    setMessages((prev) => [
      ...prev,
      { id: msgId(), role: "system", text, timestamp: now() },
    ]);
  }, []);

  // ── Handle SIGN_TX response from backend ─────────────────────────────────
  const handleSignTx = async (result: string) => {
    // Format: SIGN_TX:<eth>:<wei>:<from>:<to>
    const parts = result.split(":");
    if (parts.length < 5) return false;
    const [, ethAmt, weiAmt, fromAddr, toAddr] = parts;

    const tx: PendingTx = {
      amount_eth: parseFloat(ethAmt),
      amount_wei: weiAmt,
      from: fromAddr,
      to: toAddr,
    };
    setPendingTx(tx);
    return true;
  };

  // ── Confirm and sign the transaction ─────────────────────────────────────
  const confirmTransaction = async () => {
    if (!pendingTx || typeof window.ethereum === "undefined") return;
    setTxStatus("signing");

    try {
      const txParams = {
        from: pendingTx.from,
        to: pendingTx.to,
        value: "0x" + BigInt(pendingTx.amount_wei).toString(16),
        gas: "0x5208",
      };
      const hash = (await window.ethereum.request({
        method: "eth_sendTransaction",
        params: [txParams],
      })) as string;
      setTxHash(hash);
      setTxStatus("sent");
      pushSystemMsg(`Transaction sent! Hash: ${shortAddr(hash)}`);
      setPendingTx(null);

      // Refresh balance after 3s
      if (userWallet.address) {
        setTimeout(() => fetchUserBalance(userWallet.address), 3000);
      }
      fetchAgentInfo();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Transaction failed";
      setTxStatus("error");
      pushSystemMsg(`Transaction failed: ${msg}`);
      setPendingTx(null);
    }
  };

  // ── Send message to backend ───────────────────────────────────────────────
  const sendMessage = async (text?: string) => {
    const msgText = (text ?? input).trim();
    if (!msgText || isTyping) return;

    setInput("");

    const userMsg: ChatMessage = {
      id: msgId(),
      role: "user",
      text: msgText,
      timestamp: now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setIsTyping(true);

    try {
      const res = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: msgText,
          user_address: userWallet.address,
        }),
      });

      if (!res.ok) throw new Error(`Server error ${res.status}`);

      const data = await res.json();
      const result: string = data.result ?? "No response.";

      // Check for transaction signing request
      if (result.startsWith("SIGN_TX:")) {
        await handleSignTx(result);
        const agentMsg: ChatMessage = {
          id: msgId(),
          role: "agent",
          text: `I need your approval to transfer **${result.split(":")[1]} ETH** to the agent wallet. Please review and confirm below.`,
          timestamp: now(),
          intent: data.intent,
        };
        setMessages((prev) => [...prev, agentMsg]);
      } else {
        const agentMsg: ChatMessage = {
          id: msgId(),
          role: "agent",
          text: result,
          timestamp: now(),
          intent: data.intent,
        };
        setMessages((prev) => [...prev, agentMsg]);

        // If user checked balance, sync the UI
        if (data.intent === "check_user_balance" && userWallet.address) {
          fetchUserBalance(userWallet.address);
        }
        if (data.intent === "check_agent_balance") {
          fetchAgentInfo();
        }
      }
    } catch (err: unknown) {
      const errMsg = err instanceof Error ? err.message : "Unknown error";
      const errorMsg: ChatMessage = {
        id: msgId(),
        role: "agent",
        text: `⚠️ Could not reach the backend: ${errMsg}. Make sure the Flask server is running on port 5000.`,
        timestamp: now(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsTyping(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text).then(() => {
      setCopiedAddr(key);
      setTimeout(() => setCopiedAddr(null), 2000);
    });
  };

  // ── Fetch market status (Fear&Greed, gas, movers) ────────────────────────
  const fetchMarketStatus = async () => {
    setIsFetchingMarket(true);
    try {
      const res = await fetch(`${API_BASE}/api/market/status`);
      if (res.ok) setMarketStatus(await res.json());
    } catch { /* backend offline */ }
    finally { setIsFetchingMarket(false); }
  };

  // ── Fetch token analysis report ───────────────────────────────────────────
  const fetchMarketReport = async () => {
    setIsFetchingMarket(true);
    try {
      const roi    = parseFloat(roiInput)    || 20;
      const budget = parseFloat(budgetInput) || 1000;
      const res = await fetch(
        `${API_BASE}/api/market/analyze?roi=${roi}&budget=${budget}&top_n=8`
      );
      if (res.ok) setMarketReport(await res.json());
    } catch { /* backend offline */ }
    finally { setIsFetchingMarket(false); }
  };

  // ── Fetch RWA token list ──────────────────────────────────────────────────
  const fetchRwaTokens = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/rwa/list`);
      if (res.ok) {
        const data = await res.json();
        setRwaTokens((data.rwa_tokens ?? []).slice(0, 10));
      }
    } catch { /* ignore */ }
  };

  // Fear & Greed colour helper
  const fgColor = (v: number) =>
    v >= 60 ? "#22c55e" : v >= 40 ? "#eab308" : v >= 20 ? "#f97316" : "#ef4444";

  const riskColor = (r: string) =>
    r === "LOW" ? "#22c55e" : r === "MEDIUM" ? "#eab308" :
    r === "HIGH" ? "#f97316" : "#ef4444";

  const recoColor = (r: string) =>
    r === "BUY" || r === "ACCUMULATE" ? "#22c55e" :
    r === "WATCH" ? "#eab308" : r === "HOLD" ? "#94a3b8" : "#ef4444";

  // ─── Render ──────────────────────────────────────────────────────────────

  return (
    <PageShell>
      {/* ── Page Header ────────────────────────────────────────────────────── */}
      <div className="portfolio-page-header">
        <div className="portfolio-header-left">
          <div className="portfolio-header-icon">
            <TrendingUp size={20} strokeWidth={1.8} />
          </div>
          <div>
            <h2 className="portfolio-title">Portfolio Management Agent</h2>
            <p className="portfolio-subtitle">
              On-chain intelligence powered by LangGraph + Ethereum
            </p>
          </div>
        </div>

        <div className="portfolio-header-right">
          {/* Wallet connect / address pill */}
          {userWallet.address ? (
            <div className="portfolio-wallet-connected">
              <span className="portfolio-wallet-dot connected" />
              <span className="portfolio-wallet-addr">
                {shortAddr(userWallet.address)}
              </span>
              <button
                type="button"
                className="portfolio-icon-btn"
                title="Copy address"
                onClick={() => copyToClipboard(userWallet.address, "user")}
              >
                {copiedAddr === "user" ? (
                  <CheckCircle2 size={13} strokeWidth={2} />
                ) : (
                  <Copy size={13} strokeWidth={2} />
                )}
              </button>
              <button
                type="button"
                className="portfolio-icon-btn"
                title="Refresh balance"
                disabled={isFetchingBalance}
                onClick={() => fetchUserBalance(userWallet.address)}
              >
                <RefreshCw
                  size={13}
                  strokeWidth={2}
                  className={isFetchingBalance ? "spin" : ""}
                />
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="tf-btn primary"
              onClick={connectWallet}
            >
              <Wallet size={14} strokeWidth={2} />
              Connect Wallet
            </button>
          )}

          <button
            type="button"
            className="portfolio-icon-btn"
            title="Refresh agent info"
            disabled={isFetchingAgent}
            onClick={fetchAgentInfo}
          >
            <RefreshCw
              size={15}
              strokeWidth={2}
              className={isFetchingAgent ? "spin" : ""}
            />
          </button>
        </div>
      </div>

      {/* ── Stat Cards ─────────────────────────────────────────────────────── */}
      <div className="tf-stats-grid">
        <SummaryStatCard
          label="User Balance"
          value={
            isFetchingBalance
              ? "Loading…"
              : userWallet.address
              ? formatEth(userWallet.balance)
              : "Not connected"
          }
          icon={<Wallet size={16} strokeWidth={1.8} />}
          accent={userWallet.address ? "teal" : "muted"}
        />
        <SummaryStatCard
          label="Agent Balance"
          value={isFetchingAgent ? "Loading…" : formatEth(agentInfo.balance)}
          icon={<Bot size={16} strokeWidth={1.8} />}
          accent="blue"
        />
        <SummaryStatCard
          label="Network"
          value={userWallet.network}
          icon={<Activity size={16} strokeWidth={1.8} />}
          accent="muted"
        />
        <SummaryStatCard
          label="Agent Status"
          value={agentInfo.address ? "Online" : "Offline"}
          icon={<Shield size={16} strokeWidth={1.8} />}
          accent={agentInfo.address && !agentInfo.address.includes("offline") ? "green" : "red"}
        />
      </div>

      {/* ── Tabs ───────────────────────────────────────────────────────────── */}
      <div className="tf-tabs">
        <button
          type="button"
          className={`tf-tab ${activeTab === "chat" ? "active" : ""}`}
          onClick={() => setActiveTab("chat")}
        >
          <Bot size={14} strokeWidth={2} style={{ marginRight: 5, display: "inline" }} />
          Agent Chat
        </button>
        <button
          type="button"
          className={`tf-tab ${activeTab === "market" ? "active" : ""}`}
          onClick={() => {
            setActiveTab("market");
            if (!marketStatus) fetchMarketStatus();
          }}
        >
          <TrendingUp size={14} strokeWidth={2} style={{ marginRight: 5, display: "inline" }} />
          Market Intel
        </button>
        <button
          type="button"
          className={`tf-tab ${activeTab === "overview" ? "active" : ""}`}
          onClick={() => setActiveTab("overview")}
        >
          <BarChart3 size={14} strokeWidth={2} style={{ marginRight: 5, display: "inline" }} />
          Wallet Overview
        </button>
        <button
          type="button"
          className={`tf-tab ${activeTab === "transactions" ? "active" : ""}`}
          onClick={() => setActiveTab("transactions")}
        >
          <Zap size={14} strokeWidth={2} style={{ marginRight: 5, display: "inline" }} />
          Quick Actions
        </button>
      </div>

      {/* ══════════════════════════════════════════════════════════════════════
          TAB: AGENT CHAT
         ══════════════════════════════════════════════════════════════════════ */}
      {activeTab === "chat" && (
        <div className="portfolio-chat-layout">
          {/* Messages */}
          <div className="portfolio-chat-messages">
            {messages.map((msg) => (
              <div key={msg.id} className={`portfolio-msg portfolio-msg-${msg.role}`}>
                {msg.role !== "system" && (
                  <div className="portfolio-msg-avatar">
                    {msg.role === "agent" ? (
                      <TrendingUp size={14} strokeWidth={2} />
                    ) : (
                      <User size={14} strokeWidth={2} />
                    )}
                  </div>
                )}

                <div className="portfolio-msg-content">
                  {msg.role === "system" ? (
                    <div className="portfolio-system-notice">
                      <Activity size={12} strokeWidth={2} />
                      <span>{msg.text}</span>
                    </div>
                  ) : (
                    <>
                      <div className="portfolio-msg-bubble">
                        <pre className="portfolio-msg-text">{msg.text}</pre>
                      </div>
                      <div className="portfolio-msg-meta">
                        {msg.intent && (
                          <span className="portfolio-intent-tag">
                            {msg.intent.replace(/_/g, " ")}
                          </span>
                        )}
                        <span className="portfolio-msg-time">
                          {new Date(msg.timestamp).toLocaleTimeString([], {
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </span>
                      </div>
                    </>
                  )}
                </div>
              </div>
            ))}

            {/* Typing indicator */}
            {isTyping && (
              <div className="portfolio-msg portfolio-msg-agent">
                <div className="portfolio-msg-avatar">
                  <TrendingUp size={14} strokeWidth={2} />
                </div>
                <div className="portfolio-msg-content">
                  <div className="portfolio-msg-bubble portfolio-typing">
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                    <span className="typing-dot" />
                  </div>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* ── Pending Transaction Approval ──────────────────────────────── */}
          {pendingTx && (
            <div className="portfolio-tx-approval">
              <div className="portfolio-tx-approval-header">
                <AlertTriangle size={16} strokeWidth={2} />
                <span>Transaction Approval Required</span>
              </div>
              <div className="portfolio-tx-details">
                <div className="portfolio-tx-row">
                  <span className="portfolio-tx-label">Amount</span>
                  <span className="portfolio-tx-value accent">
                    {pendingTx.amount_eth} ETH
                  </span>
                </div>
                <div className="portfolio-tx-row">
                  <span className="portfolio-tx-label">From</span>
                  <span className="portfolio-tx-value mono">
                    {shortAddr(pendingTx.from)}
                  </span>
                </div>
                <div className="portfolio-tx-row">
                  <span className="portfolio-tx-label">To (Agent)</span>
                  <span className="portfolio-tx-value mono">
                    {shortAddr(pendingTx.to)}
                  </span>
                </div>
              </div>
              <div className="portfolio-tx-actions">
                <button
                  type="button"
                  className="tf-btn ghost"
                  onClick={() => {
                    setPendingTx(null);
                    setTxStatus("idle");
                    pushSystemMsg("Transaction cancelled by user.");
                  }}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  className="tf-btn accent"
                  disabled={txStatus === "signing"}
                  onClick={confirmTransaction}
                >
                  {txStatus === "signing" ? (
                    <>
                      <Loader2 size={13} className="spin" />
                      Signing…
                    </>
                  ) : (
                    <>
                      <CheckCircle2 size={13} strokeWidth={2} />
                      Confirm in MetaMask
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* ── TX confirmed banner ────────────────────────────────────────── */}
          {txStatus === "sent" && txHash && (
            <div className="portfolio-tx-success">
              <CheckCircle2 size={14} strokeWidth={2} />
              <span>Transaction sent · </span>
              <span className="portfolio-tx-hash">{shortAddr(txHash)}</span>
              <button
                type="button"
                className="portfolio-icon-btn"
                onClick={() => copyToClipboard(txHash, "txHash")}
                title="Copy hash"
              >
                {copiedAddr === "txHash" ? (
                  <CheckCircle2 size={12} />
                ) : (
                  <Copy size={12} />
                )}
              </button>
            </div>
          )}

          {/* ── Quick-prompt chips ─────────────────────────────────────────── */}
          <div className="portfolio-quick-prompts">
            {QUICK_PROMPTS.map((p) => (
              <button
                key={p}
                type="button"
                className="portfolio-prompt-chip"
                onClick={() => sendMessage(p)}
                disabled={isTyping}
              >
                {p}
              </button>
            ))}
          </div>

          {/* ── Input bar ─────────────────────────────────────────────────── */}
          <div className="portfolio-input-wrap">
            <div className={`portfolio-input-bar ${input ? "has-content" : ""}`}>
              <textarea
                ref={inputRef}
                className="portfolio-input"
                value={input}
                placeholder="Ask the agent — e.g. 'Check my balance' or 'Transfer 0.01 ETH'"
                rows={1}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isTyping}
              />
              <button
                type="button"
                className="portfolio-send-btn"
                disabled={!input.trim() || isTyping}
                onClick={() => sendMessage()}
                title="Send"
              >
                {isTyping ? (
                  <Loader2 size={15} className="spin" />
                ) : (
                  <Send size={15} strokeWidth={2} />
                )}
              </button>
            </div>
            <span className="portfolio-input-hint">
              Press <strong>Enter</strong> to send · <strong>Shift+Enter</strong> for new line
            </span>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          TAB: MARKET INTELLIGENCE
         ══════════════════════════════════════════════════════════════════════ */}
      {activeTab === "market" && (
        <div className="portfolio-market-layout">

          {/* ── Row 1: Market Status bar ──────────────────────────────────── */}
          <div className="portfolio-market-status-bar">
            {marketStatus ? (
              <>
                <div className="portfolio-fg-pill" style={{ borderColor: fgColor(marketStatus.fear_greed.value) }}>
                  <span className="portfolio-fg-label">Fear & Greed</span>
                  <span className="portfolio-fg-value" style={{ color: fgColor(marketStatus.fear_greed.value) }}>
                    {marketStatus.fear_greed.value}/100
                  </span>
                  <span className="portfolio-fg-tag">{marketStatus.fear_greed.label}</span>
                </div>
                <div className="portfolio-gas-pill">
                  <Zap size={12} strokeWidth={2} />
                  <span>Gas: {marketStatus.gas?.standard_gwei ?? "—"} Gwei</span>
                </div>
                <div className="portfolio-movers-inline">
                  {marketStatus.gainers_24h.slice(0, 3).map((t) => (
                    <span key={t.symbol} className="portfolio-mover-chip up">
                      {t.symbol} +{t.change_24h.toFixed(1)}%
                    </span>
                  ))}
                  {marketStatus.losers_24h.slice(0, 2).map((t) => (
                    <span key={t.symbol} className="portfolio-mover-chip down">
                      {t.symbol} {t.change_24h.toFixed(1)}%
                    </span>
                  ))}
                </div>
                <span className="portfolio-data-age">{marketStatus.data_age_min.toFixed(0)} min ago</span>
              </>
            ) : (
              <span className="portfolio-market-offline">
                {isFetchingMarket ? <><Loader2 size={13} className="spin" /> Loading market data…</> : "Market data not loaded"}
              </span>
            )}
            <button type="button" className="portfolio-icon-btn" onClick={fetchMarketStatus} disabled={isFetchingMarket} title="Refresh">
              <RefreshCw size={13} strokeWidth={2} className={isFetchingMarket ? "spin" : ""} />
            </button>
          </div>

          {/* ── Row 2: ROI Analyzer controls ──────────────────────────────── */}
          <div className="portfolio-analyzer-controls">
            <div className="portfolio-analyzer-field">
              <label>ROI Target (%)</label>
              <input type="number" value={roiInput} min="5" max="500"
                onChange={(e) => setRoiInput(e.target.value)} className="portfolio-analyzer-input" />
            </div>
            <div className="portfolio-analyzer-field">
              <label>Budget (USD)</label>
              <input type="number" value={budgetInput} min="100"
                onChange={(e) => setBudgetInput(e.target.value)} className="portfolio-analyzer-input" />
            </div>
            <button type="button" className="tf-btn primary"
              onClick={() => { fetchMarketReport(); fetchRwaTokens(); }}
              disabled={isFetchingMarket}>
              {isFetchingMarket ? <><Loader2 size={13} className="spin" /> Analyzing…</> : <><BarChart3 size={13} /> Analyze</>}
            </button>
          </div>

          {/* ── Row 3: Top Picks table ─────────────────────────────────────── */}
          {marketReport && (
            <>
              {/* Warning banner */}
              {marketReport.warnings?.length > 0 && (
                <div className="portfolio-market-warn">
                  <AlertTriangle size={13} strokeWidth={2} />
                  <span>{marketReport.warnings[0].slice(0, 120)}</span>
                </div>
              )}

              {/* Portfolio summary */}
              <div className="portfolio-alloc-summary">
                <span className="portfolio-alloc-label">
                  Analyzed <strong>{marketReport.tokens_analyzed}</strong> tokens ·{" "}
                  <strong>{marketReport.hits_target_count}</strong> hit {marketReport.roi_target_pct}% target
                </span>
                {marketReport.portfolio.status === "OK" && (
                  <span className="portfolio-alloc-roi"
                    style={{ color: marketReport.portfolio.hits_target ? "#22c55e" : "#f97316" }}>
                    Portfolio projected: +{marketReport.portfolio.projected_roi_pct.toFixed(1)}%
                    {marketReport.portfolio.hits_target ? " ✓" : " (below target)"}
                  </span>
                )}
              </div>

              {/* Top picks table */}
              <div className="portfolio-picks-table">
                <div className="portfolio-picks-header">
                  <span>#</span><span>Token</span><span>Price</span>
                  <span>Score</span><span>ROI 12m</span><span>RSI</span>
                  <span>Risk</span><span>Signal</span>
                </div>
                {marketReport.top_picks.map((t, i) => (
                  <div key={t.symbol} className="portfolio-picks-row">
                    <span className="portfolio-picks-rank">#{i + 1}</span>
                    <span className="portfolio-picks-symbol">
                      <strong>{t.symbol}</strong>
                      {t.apy_pct > 0 && <small> {t.apy_pct}% APY</small>}
                    </span>
                    <span className="portfolio-picks-price">${t.current_price < 0.01 ? t.current_price.toFixed(6) : t.current_price.toFixed(4)}</span>
                    <span className="portfolio-picks-score">{t.composite_score.toFixed(0)}</span>
                    <span className="portfolio-picks-roi"
                      style={{ color: t.projected_roi_pct >= (marketReport.roi_target_pct ?? 20) ? "#22c55e" : "#f97316" }}>
                      {t.projected_roi_pct > 0 ? "+" : ""}{t.projected_roi_pct.toFixed(1)}%
                    </span>
                    <span className="portfolio-picks-rsi">{t.rsi ? t.rsi.toFixed(0) : "—"}</span>
                    <span className="portfolio-picks-risk" style={{ color: riskColor(t.risk_label) }}>
                      {t.risk_label}
                    </span>
                    <span className="portfolio-picks-reco" style={{ color: recoColor(t.recommendation) }}>
                      {t.recommendation}
                    </span>
                  </div>
                ))}
              </div>

              {/* Portfolio allocations */}
              {marketReport.portfolio.status === "OK" && marketReport.portfolio.allocations.length > 0 && (
                <div className="portfolio-alloc-section">
                  <h4 className="portfolio-alloc-title">Suggested Allocation · ${marketReport.budget_usd.toFixed(0)} budget</h4>
                  <div className="portfolio-alloc-grid">
                    {marketReport.portfolio.allocations.map((a) => (
                      <div key={a.symbol} className="portfolio-alloc-card">
                        <div className="portfolio-alloc-card-top">
                          <span className="portfolio-alloc-sym">{a.symbol}</span>
                          <span className="portfolio-alloc-pct">{a.alloc_pct.toFixed(0)}%</span>
                        </div>
                        <div className="portfolio-alloc-card-body">
                          <div>${a.alloc_usd.toFixed(0)} → buy @ ${a.buy_price.toFixed(4)}</div>
                          <div>Target: ${a.target_price.toFixed(4)}</div>
                          <div style={{ color: "#22c55e" }}>+{a.projected_roi.toFixed(1)}% projected</div>
                          <div style={{ color: riskColor(a.risk_label), fontSize: "0.7rem" }}>{a.risk_label} risk</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}

          {/* ── Row 4: RWA Tokens table ────────────────────────────────────── */}
          {rwaTokens.length > 0 && (
            <div className="portfolio-rwa-section">
              <h4 className="portfolio-rwa-title">
                <Shield size={14} strokeWidth={2} /> Top RWA Tokens
              </h4>
              <div className="portfolio-picks-table">
                <div className="portfolio-picks-header">
                  <span>Token</span><span>Price</span><span>Market Cap</span>
                  <span>TVL</span><span>APY</span><span>Trust</span><span>Badge</span>
                </div>
                {rwaTokens.map((r) => (
                  <div key={r.id} className="portfolio-picks-row">
                    <span className="portfolio-picks-symbol"><strong>{r.symbol}</strong></span>
                    <span>${r.price_usd < 0.01 ? r.price_usd?.toFixed(6) : r.price_usd?.toFixed(4)}</span>
                    <span>{r.market_cap ? "$" + (r.market_cap / 1e6).toFixed(0) + "M" : "—"}</span>
                    <span>{r.tvl_usd ? "$" + (r.tvl_usd / 1e6).toFixed(0) + "M" : "—"}</span>
                    <span style={{ color: "#22c55e" }}>{r.apy_pct ? r.apy_pct + "%" : "—"}</span>
                    <span>{r.trust_score}/100</span>
                    <span style={{ fontSize: "0.7rem", opacity: 0.8 }}>{r.trust_badge}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Empty state ────────────────────────────────────────────────── */}
          {!marketReport && !isFetchingMarket && (
            <div className="portfolio-market-empty">
              <BarChart3 size={36} strokeWidth={1.4} />
              <p>Set your ROI target and budget, then click <strong>Analyze</strong> to rank all tokens.</p>
              <button type="button" className="tf-btn primary" onClick={() => { fetchMarketStatus(); fetchMarketReport(); fetchRwaTokens(); }}>
                <TrendingUp size={14} /> Run Full Analysis
              </button>
            </div>
          )}
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          TAB: WALLET OVERVIEW
         ══════════════════════════════════════════════════════════════════════ */}
      {activeTab === "overview" && (
        <div className="portfolio-overview-grid">

          {/* User Wallet Card */}
          <div className="portfolio-wallet-card">
            <div className="portfolio-card-header">
              <div className="portfolio-card-icon">
                <Wallet size={18} strokeWidth={1.8} />
              </div>
              <div>
                <h3 className="portfolio-card-title">Your Wallet</h3>
                <p className="portfolio-card-sub">MetaMask Connected</p>
              </div>
              <StatusBadge
                variant={userWallet.address ? "connected" : "disconnected"}
              />
            </div>

            {userWallet.address ? (
              <>
                <div className="portfolio-address-row">
                  <code className="portfolio-address">{userWallet.address}</code>
                  <button
                    type="button"
                    className="portfolio-icon-btn"
                    onClick={() => copyToClipboard(userWallet.address, "user-card")}
                    title="Copy address"
                  >
                    {copiedAddr === "user-card" ? (
                      <CheckCircle2 size={13} />
                    ) : (
                      <Copy size={13} />
                    )}
                  </button>
                </div>
                <div className="portfolio-balance-display">
                  <span className="portfolio-balance-label">Balance</span>
                  <span className="portfolio-balance-value">
                    {isFetchingBalance ? (
                      <Loader2 size={16} className="spin" />
                    ) : (
                      formatEth(userWallet.balance)
                    )}
                  </span>
                </div>
                <div className="portfolio-network-badge">
                  <Activity size={12} strokeWidth={2} />
                  {userWallet.network}
                </div>
                <button
                  type="button"
                  className="tf-btn secondary full"
                  onClick={() => fetchUserBalance(userWallet.address)}
                  disabled={isFetchingBalance}
                >
                  <RefreshCw
                    size={13}
                    strokeWidth={2}
                    className={isFetchingBalance ? "spin" : ""}
                  />
                  Refresh Balance
                </button>
              </>
            ) : (
              <div className="portfolio-wallet-empty">
                <Wallet size={32} strokeWidth={1.4} />
                <p>No wallet connected</p>
                <button
                  type="button"
                  className="tf-btn primary"
                  onClick={connectWallet}
                >
                  Connect MetaMask
                </button>
              </div>
            )}
          </div>

          {/* Agent Wallet Card */}
          <div className="portfolio-wallet-card">
            <div className="portfolio-card-header">
              <div className="portfolio-card-icon agent">
                <Bot size={18} strokeWidth={1.8} />
              </div>
              <div>
                <h3 className="portfolio-card-title">Agent Wallet</h3>
                <p className="portfolio-card-sub">LangGraph Managed</p>
              </div>
              <StatusBadge
                variant={
                  agentInfo.address && !agentInfo.address.includes("offline")
                    ? "connected"
                    : "disconnected"
                }
              />
            </div>

            {agentInfo.address && !agentInfo.address.includes("offline") ? (
              <>
                <div className="portfolio-address-row">
                  <code className="portfolio-address">{agentInfo.address}</code>
                  <button
                    type="button"
                    className="portfolio-icon-btn"
                    onClick={() => copyToClipboard(agentInfo.address, "agent-card")}
                    title="Copy address"
                  >
                    {copiedAddr === "agent-card" ? (
                      <CheckCircle2 size={13} />
                    ) : (
                      <Copy size={13} />
                    )}
                  </button>
                </div>
                <div className="portfolio-balance-display">
                  <span className="portfolio-balance-label">Balance</span>
                  <span className="portfolio-balance-value">
                    {isFetchingAgent ? (
                      <Loader2 size={16} className="spin" />
                    ) : (
                      formatEth(agentInfo.balance)
                    )}
                  </span>
                </div>
                <div className="portfolio-network-badge">
                  <Activity size={12} strokeWidth={2} />
                  Ethereum Sepolia
                </div>
                <button
                  type="button"
                  className="tf-btn secondary full"
                  onClick={fetchAgentInfo}
                  disabled={isFetchingAgent}
                >
                  <RefreshCw
                    size={13}
                    strokeWidth={2}
                    className={isFetchingAgent ? "spin" : ""}
                  />
                  Refresh
                </button>
              </>
            ) : (
              <div className="portfolio-wallet-empty">
                <Bot size={32} strokeWidth={1.4} />
                <p>Backend offline</p>
                <button
                  type="button"
                  className="tf-btn secondary"
                  onClick={fetchAgentInfo}
                >
                  Retry
                </button>
              </div>
            )}
          </div>

          {/* Agent Capabilities Card */}
          <div className="portfolio-wallet-card capabilities-card">
            <div className="portfolio-card-header">
              <div className="portfolio-card-icon">
                <Zap size={18} strokeWidth={1.8} />
              </div>
              <div>
                <h3 className="portfolio-card-title">Agent Capabilities</h3>
                <p className="portfolio-card-sub">Supported intents</p>
              </div>
            </div>
            <div className="portfolio-caps-list">
              {[
                {
                  icon: <Wallet size={14} />,
                  label: "Check User Balance",
                  desc: "Read your MetaMask wallet's ETH balance",
                },
                {
                  icon: <Bot size={14} />,
                  label: "Check Agent Balance",
                  desc: "Read the agent wallet's ETH balance",
                },
                {
                  icon: <ArrowUpRight size={14} />,
                  label: "Transfer to Agent",
                  desc: "Send ETH from your wallet to the agent",
                },
                {
                  icon: <PlusCircle size={14} />,
                  label: "Create Wallet",
                  desc: "Generate a new Ethereum wallet keypair",
                },
              ].map((cap) => (
                <div key={cap.label} className="portfolio-cap-item">
                  <div className="portfolio-cap-icon">{cap.icon}</div>
                  <div>
                    <div className="portfolio-cap-label">{cap.label}</div>
                    <div className="portfolio-cap-desc">{cap.desc}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ══════════════════════════════════════════════════════════════════════
          TAB: QUICK ACTIONS
         ══════════════════════════════════════════════════════════════════════ */}
      {activeTab === "transactions" && (
        <div className="portfolio-actions-grid">

          {/* Check balances */}
          <div className="portfolio-action-card">
            <div className="portfolio-action-icon">
              <DollarSign size={20} strokeWidth={1.8} />
            </div>
            <h3 className="portfolio-action-title">Check Balances</h3>
            <p className="portfolio-action-desc">
              Fetch live ETH balances for both your wallet and the agent wallet.
            </p>
            <div className="portfolio-action-btns">
              <button
                type="button"
                className="tf-btn primary"
                disabled={isTyping}
                onClick={() => {
                  setActiveTab("chat");
                  sendMessage("Check my wallet balance");
                }}
              >
                <ArrowDownLeft size={13} strokeWidth={2} />
                My Balance
              </button>
              <button
                type="button"
                className="tf-btn secondary"
                disabled={isTyping}
                onClick={() => {
                  setActiveTab("chat");
                  sendMessage("Check agent wallet balance");
                }}
              >
                <Bot size={13} strokeWidth={2} />
                Agent Balance
              </button>
            </div>
          </div>

          {/* Transfer ETH */}
          <div className="portfolio-action-card">
            <div className="portfolio-action-icon amber">
              <ArrowUpRight size={20} strokeWidth={1.8} />
            </div>
            <h3 className="portfolio-action-title">Transfer ETH</h3>
            <p className="portfolio-action-desc">
              Send ETH from your connected wallet to the agent. MetaMask will prompt you to sign.
            </p>
            <TransferForm
              disabled={isTyping || !userWallet.address}
              onTransfer={(amount) => {
                setActiveTab("chat");
                sendMessage(`Transfer ${amount} ETH to agent`);
              }}
              walletConnected={!!userWallet.address}
            />
          </div>

          {/* Create wallet */}
          <div className="portfolio-action-card">
            <div className="portfolio-action-icon green">
              <PlusCircle size={20} strokeWidth={1.8} />
            </div>
            <h3 className="portfolio-action-title">Create New Wallet</h3>
            <p className="portfolio-action-desc">
              Generate a brand-new Ethereum wallet. The private key will be returned — save it securely.
            </p>
            <button
              type="button"
              className="tf-btn accent full"
              disabled={isTyping}
              onClick={() => {
                setActiveTab("chat");
                sendMessage("Create a new wallet");
              }}
            >
              <PlusCircle size={13} strokeWidth={2} />
              Generate Wallet
            </button>
          </div>
        </div>
      )}
    </PageShell>
  );
};

// ─── Transfer Form Sub-Component ─────────────────────────────────────────────

interface TransferFormProps {
  disabled: boolean;
  walletConnected: boolean;
  onTransfer: (amount: string) => void;
}

const TransferForm = ({ disabled, walletConnected, onTransfer }: TransferFormProps) => {
  const [amount, setAmount] = useState("0.01");

  const presets = ["0.001", "0.005", "0.01", "0.05"];

  return (
    <div className="portfolio-transfer-form">
      <div className="portfolio-transfer-presets">
        {presets.map((p) => (
          <button
            key={p}
            type="button"
            className={`portfolio-preset-btn ${amount === p ? "active" : ""}`}
            onClick={() => setAmount(p)}
            disabled={disabled}
          >
            {p}
          </button>
        ))}
      </div>
      <div className="portfolio-transfer-input-row">
        <input
          type="number"
          className="portfolio-transfer-input"
          value={amount}
          min="0.0001"
          step="0.001"
          onChange={(e) => setAmount(e.target.value)}
          disabled={disabled}
          placeholder="Amount in ETH"
        />
        <span className="portfolio-transfer-unit">ETH</span>
      </div>
      {!walletConnected && (
        <p className="portfolio-transfer-warn">
          <AlertTriangle size={12} strokeWidth={2} />
          Connect your wallet first
        </p>
      )}
      <button
        type="button"
        className="tf-btn accent full"
        disabled={disabled || !walletConnected || !amount || parseFloat(amount) <= 0}
        onClick={() => onTransfer(amount)}
      >
        <ArrowUpRight size={13} strokeWidth={2} />
        Transfer {amount || "…"} ETH
      </button>
    </div>
  );
};

export default PortfolioPage;
