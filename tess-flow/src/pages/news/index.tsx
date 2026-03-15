import { useState, useEffect } from "react";
import { ExternalLink, RefreshCw, Loader2, TrendingUp, TrendingDown, Zap, Shield } from "lucide-react";
import PageShell from "../../shared/PageShell";

const API_BASE = "http://localhost:5000";

interface Mover { symbol: string; change_24h: number; price_usd: number; }
interface MarketStatus {
  fear_greed: { value: number; label: string };
  gas: { slow_gwei: number; standard_gwei: number; fast_gwei: number };
  gainers_24h: Mover[];
  losers_24h: Mover[];
  tokens_total: number;
  data_age_min: number;
}
interface RwaToken {
  id: string; symbol: string; name: string;
  price_usd: number; market_cap: number; tvl_usd: number;
  apy_pct: number; trust_score: number; trust_badge: string;
}

const makeImage = (seed: string) =>
  `https://picsum.photos/seed/tessflow-${seed}/960/540`;

// Static story placeholders (shown when live data unavailable)
const STATIC_NEWS = [
  { id: "n-1", title: "Agent wallet policy engines are becoming default in production Web3 automation stacks", source: "The Block", time: "07:05 UTC", summary: "Teams are replacing manual approval loops with enforceable policy rails.", image: makeImage("wallet-policy"), url: "https://explorer.tesseris.org" },
  { id: "n-2", title: "DeFi treasury teams pilot autonomous rebalancers with deterministic stop-loss constraints", source: "Bankless", time: "07:18 UTC", summary: "Early deployments report better capture with clearer downside controls.", image: makeImage("defi-rebalance"), url: "https://explorer.tesseris.org" },
  { id: "n-3", title: "MCP connector standard gains adoption across chain analytics and custody providers", source: "Messari", time: "07:29 UTC", summary: "A common connector pattern is reducing integration effort for teams.", image: makeImage("mcp-connectors"), url: "https://explorer.tesseris.org" },
  { id: "n-4", title: "Inference proof infrastructure cuts cost for onchain verification of AI outputs", source: "a16z Crypto", time: "07:46 UTC", summary: "Recent performance gains are making verifiable inference more practical.", image: makeImage("zk-inference"), url: "https://explorer.tesseris.org" },
  { id: "n-5", title: "Stablecoin settlement agents expand from pilot to cross-border B2B operations", source: "CoinDesk", time: "08:02 UTC", summary: "Operations teams are scaling automated flows with stronger audit paths.", image: makeImage("stablecoin-settlement"), url: "https://explorer.tesseris.org" },
];

const fgColor = (v: number) =>
  v >= 60 ? "#22c55e" : v >= 40 ? "#eab308" : v >= 20 ? "#f97316" : "#ef4444";

const NewsPage = () => {
  const [market, setMarket]         = useState<MarketStatus | null>(null);
  const [rwaTokens, setRwaTokens]   = useState<RwaToken[]>([]);
  const [loading, setLoading]       = useState(true);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  const fetchData = async () => {
    setLoading(true);
    try {
      const [mRes, rRes] = await Promise.all([
        fetch(`${API_BASE}/api/market/status`),
        fetch(`${API_BASE}/api/rwa/list`),
      ]);
      if (mRes.ok) setMarket(await mRes.json());
      if (rRes.ok) {
        const d = await rRes.json();
        setRwaTokens((d.rwa_tokens ?? []).slice(0, 8));
      }
      setLastUpdated(new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }));
    } catch { /* backend offline — static content shown */ }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchData(); }, []);

  // Build brief from live data or fallback
  const dailyBrief = market
    ? {
        lead: `Market Fear & Greed: ${market.fear_greed.value}/100 (${market.fear_greed.label}). Gas at ${market.gas?.standard_gwei ?? "—"} Gwei standard.`,
        points: [
          { label: "Top Gainers 24h", text: market.gainers_24h.slice(0, 3).map((t) => `${t.symbol} +${t.change_24h.toFixed(1)}%`).join(" · ") || "No data" },
          { label: "Top Losers 24h",  text: market.losers_24h.slice(0, 3).map((t) => `${t.symbol} ${t.change_24h.toFixed(1)}%`).join(" · ") || "No data" },
          { label: "Watch Next",      text: market.fear_greed.value < 30 ? "Extreme Fear — historically good entry zone. Watch for reversal signals." : market.fear_greed.value > 70 ? "Greed zone — consider taking partial profits, tighten stops." : "Neutral zone — trend-follow with normal position sizing." },
        ],
      }
    : {
        lead: "AI + Web3 automation is shifting from experimentation to policy-governed production.",
        points: [
          { label: "What Changed", text: "Wallet guardrails and treasury controls are becoming default, not optional, across production workflows." },
          { label: "Why It Matters", text: "Teams that pair speed with deterministic controls are showing higher reliability and cleaner audit trails." },
          { label: "Watch Next", text: "Adoption should accelerate as observability and verification tooling becomes easier to operationalize." },
        ],
      };

  return (
    <PageShell className="tf-news-page">

      {/* ── Live Market Banner ─────────────────────────────────────────── */}
      {market && (
        <div className="tf-news-live-bar">
          <div className="tf-news-fg-chip" style={{ color: fgColor(market.fear_greed.value), borderColor: fgColor(market.fear_greed.value) }}>
            <span className="tf-news-fg-num">{market.fear_greed.value}</span>
            <span className="tf-news-fg-label">{market.fear_greed.label}</span>
          </div>
          <div className="tf-news-gas-chip">
            <Zap size={11} strokeWidth={2} />
            {market.gas?.standard_gwei ?? "—"} Gwei
          </div>
          <div className="tf-news-movers">
            {market.gainers_24h.slice(0, 3).map((t) => (
              <span key={t.symbol} className="tf-news-mover up">
                <TrendingUp size={10} strokeWidth={2} />
                {t.symbol} +{t.change_24h.toFixed(1)}%
              </span>
            ))}
            {market.losers_24h.slice(0, 2).map((t) => (
              <span key={t.symbol} className="tf-news-mover down">
                <TrendingDown size={10} strokeWidth={2} />
                {t.symbol} {t.change_24h.toFixed(1)}%
              </span>
            ))}
          </div>
          <div className="tf-news-live-right">
            {lastUpdated && <span className="tf-news-updated">Updated {lastUpdated}</span>}
            <button type="button" className="tf-news-refresh-btn" onClick={fetchData} disabled={loading} title="Refresh">
              <RefreshCw size={12} strokeWidth={2} className={loading ? "spin" : ""} />
            </button>
          </div>
        </div>
      )}

      <div className="tf-news-top-layout">
        {/* ── Latest Stories ─────────────────────────────────────────────── */}
        <section className="tf-news-section tf-news-latest-section">
          <div className="tf-news-section-head">
            <div>
              <h2>Latest Market News</h2>
              <p>Top 5 stories · {new Date().toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}</p>
            </div>
            {loading && <Loader2 size={15} className="spin" style={{ color: "var(--text-muted)" }} />}
          </div>

          <div className="tf-news-list">
            {STATIC_NEWS.map((article, index) => (
              <article key={article.id} className="tf-news-list-item">
                <div className="tf-news-list-thumb-wrap">
                  <img src={article.image} alt={article.title} className="tf-news-list-thumb" loading="lazy" />
                </div>
                <div className="tf-news-list-content">
                  <div className="tf-news-list-meta">
                    <span className="tf-news-rank">#{index + 1}</span>
                    <span className="tf-news-source">{article.source}</span>
                    <span className="tf-news-dot">•</span>
                    <span className="tf-news-time">{article.time}</span>
                  </div>
                  <h3>{article.title}</h3>
                  <p>{article.summary}</p>
                  <button type="button" className="tf-news-inline-link"
                    onClick={() => window.open(article.url, "_blank", "noopener,noreferrer")}>
                    Read story <ExternalLink size={12} strokeWidth={2.2} />
                  </button>
                </div>
              </article>
            ))}
          </div>
        </section>

        {/* ── Right Rail ─────────────────────────────────────────────────── */}
        <aside className="tf-news-rail">
          <section className="tf-news-rail-card tf-news-brief-card">
            <div className="tf-news-brief-head">
              <h3>Daily Brief</h3>
              <span className="tf-news-brief-count">{market ? "Live" : "Summary"}</span>
            </div>
            <p className="tf-news-brief-lead">{dailyBrief.lead}</p>
            <div className="tf-news-brief-summary">
              {dailyBrief.points.map((point) => (
                <div key={point.label} className="tf-news-brief-point">
                  <span>{point.label}</span>
                  <p>{point.text}</p>
                </div>
              ))}
            </div>
          </section>

          {/* ── RWA Spotlight ──────────────────────────────────────────────── */}
          {rwaTokens.length > 0 && (
            <section className="tf-news-rail-card tf-news-rwa-card">
              <div className="tf-news-brief-head">
                <h3><Shield size={13} strokeWidth={2} style={{ display: "inline", marginRight: 5 }} />RWA Spotlight</h3>
                <span className="tf-news-brief-count">Live</span>
              </div>
              <div className="tf-news-rwa-list">
                {rwaTokens.map((r) => (
                  <div key={r.id} className="tf-news-rwa-row">
                    <div className="tf-news-rwa-left">
                      <span className="tf-news-rwa-sym">{r.symbol}</span>
                      <span className="tf-news-rwa-badge">{r.trust_badge}</span>
                    </div>
                    <div className="tf-news-rwa-right">
                      <span className="tf-news-rwa-price">
                        ${r.price_usd < 0.01 ? r.price_usd.toFixed(6) : r.price_usd.toFixed(3)}
                      </span>
                      {r.apy_pct > 0 && (
                        <span className="tf-news-rwa-apy">{r.apy_pct}% APY</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>
          )}
        </aside>
      </div>

      {/* ── RWA Full Table (if data available) ─────────────────────────── */}
      {rwaTokens.length > 0 && (
        <section className="tf-news-section">
          <div className="tf-news-section-head">
            <div>
              <h2>RWA Token Rankings</h2>
              <p>Live trust scores · TVL · APY from on-chain data</p>
            </div>
          </div>
          <div className="tf-news-rwa-table">
            <div className="tf-news-rwa-thead">
              <span>#</span><span>Token</span><span>Price</span>
              <span>Market Cap</span><span>TVL</span><span>APY</span>
              <span>Trust</span><span>Status</span>
            </div>
            {rwaTokens.map((r, i) => (
              <div key={r.id} className="tf-news-rwa-trow">
                <span className="tf-news-rwa-rank">#{i + 1}</span>
                <span className="tf-news-rwa-name">
                  <strong>{r.symbol}</strong>
                  <small>{r.name.slice(0, 18)}</small>
                </span>
                <span className="tf-news-rwa-td mono">
                  ${r.price_usd < 0.01 ? r.price_usd.toFixed(6) : r.price_usd.toFixed(4)}
                </span>
                <span className="tf-news-rwa-td">
                  {r.market_cap ? "$" + (r.market_cap / 1e6).toFixed(0) + "M" : "—"}
                </span>
                <span className="tf-news-rwa-td">
                  {r.tvl_usd ? "$" + (r.tvl_usd / 1e6).toFixed(0) + "M" : "—"}
                </span>
                <span className="tf-news-rwa-td apy">
                  {r.apy_pct ? r.apy_pct + "%" : "—"}
                </span>
                <span className="tf-news-rwa-td trust">{r.trust_score}/100</span>
                <span className="tf-news-rwa-td badge">{r.trust_badge}</span>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* ── Archive ─────────────────────────────────────────────────────── */}
      <section className="tf-news-section">
        <div className="tf-news-section-head">
          <div><h2>Previous Market Insights</h2><p>Browse past daily briefings</p></div>
        </div>
        <div className="tf-news-archive-grid">
          {[
            { id: "p-1", title: "Daily Market Insight: Mar 11", date: "March 11, 2026", summary: "Infra-heavy cycle led by reliability and observability updates.", image: makeImage("insight-mar11") },
            { id: "p-2", title: "Daily Market Insight: Mar 09", date: "March 9, 2026",  summary: "Liquidity, custody and wallet orchestration themes dominated.", image: makeImage("insight-mar09") },
            { id: "p-3", title: "Daily Market Insight: Feb 26", date: "February 26, 2026", summary: "Compliance and enterprise deployment patterns shaped sentiment.", image: makeImage("insight-feb26") },
            { id: "p-4", title: "Daily Market Insight: Dec 14", date: "December 14, 2025", summary: "Platform interoperability and orchestration reliability stayed central.", image: makeImage("insight-dec14") },
          ].map((insight) => (
            <article key={insight.id} className="tf-news-archive-card">
              <div className="tf-news-archive-thumb-wrap">
                <img src={insight.image} alt={insight.title} className="tf-news-archive-thumb" loading="lazy" />
              </div>
              <div className="tf-news-archive-content">
                <span className="tf-news-archive-date">{insight.date}</span>
                <h3>{insight.title}</h3>
                <p>{insight.summary}</p>
                <button type="button" className="tf-news-inline-link"
                  onClick={() => window.open("https://explorer.tesseris.org", "_blank", "noopener,noreferrer")}>
                  Open briefing <ExternalLink size={12} strokeWidth={2.2} />
                </button>
              </div>
            </article>
          ))}
        </div>
      </section>
    </PageShell>
  );
};

export default NewsPage;
