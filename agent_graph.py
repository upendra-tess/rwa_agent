"""
agent_graph.py — LangGraph Agent State Machine
================================================
Routes user messages to the correct handler nodes.

Original nodes (wallet ops):
  check_user_balance   → ETH balance
  check_agent_balance  → agent wallet balance
  transfer_to_agent    → MetaMask transfer
  create_wallet        → generate new wallet

New nodes (trading intelligence):
  analyze_market       → run full token analysis (20% ROI pipeline)
  suggest_trades       → build gas/slippage-aware trade plan
  token_info           → deep analysis of a single token
  market_status        → fear/greed + top movers summary
  verify_rwa           → trust score for a specific RWA token

Intent routing table (handled by Claude via intent_parser.py):
  "check_user_balance"   → check_user_balance
  "check_agent_balance"  → check_agent_balance
  "transfer_to_agent"    → transfer_to_agent
  "create_wallet"        → create_wallet
  "analyze_market"       → analyze_market
  "suggest_trades"       → suggest_trades
  "token_info"           → token_info
  "market_status"        → market_status
  "verify_rwa"           → verify_rwa
  anything else          → handle_unknown
"""

import logging
from langgraph.graph import StateGraph, END

from state import AgentState
from intent_parser import parse_intent
from wallet_tools import (
    check_user_balance,
    check_agent_balance,
    transfer_to_agent,
    create_wallet,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Fallback Handler
# ═══════════════════════════════════════════════════════════════════════════════

def handle_unknown(state: AgentState) -> dict:
    return {
        "result": (
            "I didn't understand that. Here's what I can do:\n\n"
            "**Wallet Operations:**\n"
            "• Check your wallet balance\n"
            "• Check the agent wallet balance\n"
            "• Transfer ETH to the agent wallet\n"
            "• Create a new Ethereum wallet\n\n"
            "**Trading Intelligence:**\n"
            "• Analyze the market for a target ROI (e.g. 'I want 20% ROI in 1 year')\n"
            "• Suggest trades with gas + slippage protection\n"
            "• Get info on a specific token (e.g. 'tell me about ONDO')\n"
            "• Get current market status (Fear & Greed, top movers)\n"
            "• Verify a RWA token's trust score (e.g. 'verify ondo-finance')\n"
        )
    }


# ═══════════════════════════════════════════════════════════════════════════════
# NEW: Trading Intelligence Nodes
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_market(state: AgentState) -> dict:
    """
    Full market analysis with ROI target + portfolio allocation.
    Triggered by: 'I want 20% ROI', 'analyze market', 'best tokens to buy'
    """
    try:
        from trading_analyzer import analyze_all_tokens, format_analysis_for_chat
        from data_pipeline import get_data_freshness

        # Extract ROI target from user input (default 20%)
        roi_target = _extract_roi(state.get("user_input", ""), default=20.0)
        budget     = _extract_budget(state.get("amount", ""), default=1000.0)

        # Check data freshness — warn if stale
        freshness = get_data_freshness()
        stale_warning = ""
        if not freshness["is_fresh"]:
            stale_warning = (
                f"\n\n⚠️ *Market data is {freshness['age_minutes']:.0f} minutes old — "
                "refreshing in background.*"
            )

        # Run analysis
        report = analyze_all_tokens(
            roi_target_pct=roi_target,
            budget_usd=budget,
            top_n=8,
        )
        result = format_analysis_for_chat(report) + stale_warning
        return {"result": result}

    except Exception as e:
        logger.error("[agent] analyze_market error: %s", e, exc_info=True)
        return {"result": f"Analysis error: {e}. Please try again."}


def suggest_trades(state: AgentState) -> dict:
    """
    Build a complete gas/slippage-aware trade execution plan.
    Triggered by: 'suggest trades', 'how should I trade', 'execute strategy'
    """
    try:
        from trading_strategy import get_full_trading_plan, format_plan_for_chat

        roi_target = _extract_roi(state.get("user_input", ""), default=20.0)
        budget     = _extract_budget(state.get("amount", ""), default=1000.0)

        plan = get_full_trading_plan(
            roi_target_pct=roi_target,
            budget_usd=budget,
        )
        result = format_plan_for_chat(plan)
        return {"result": result}

    except Exception as e:
        logger.error("[agent] suggest_trades error: %s", e, exc_info=True)
        return {"result": f"Strategy error: {e}. Please try again."}


def token_info(state: AgentState) -> dict:
    """
    Deep analysis of a single token.
    Triggered by: 'tell me about ONDO', 'analyze ETH', 'what is LINK doing'
    """
    try:
        from trading_analyzer import analyze_token

        # Extract token from user input
        token_id = _extract_token_id(state.get("user_input", ""),
                                      state.get("token_id", ""))
        if not token_id:
            return {
                "result": (
                    "Which token would you like me to analyze? "
                    "For example: 'analyze ondo-finance' or 'tell me about ETH'"
                )
            }

        analysis = analyze_token(token_id)
        if not analysis:
            return {"result": f"Token '{token_id}' not found in database. "
                              "Try using the CoinGecko ID (e.g. 'ondo-finance', 'ethereum')."}

        lines = [
            f"## {analysis['symbol']} — {analysis['name']}",
            f"",
            f"**Price:** ${analysis['current_price']:.4f}  |  "
            f"**Market Cap:** ${analysis['market_cap']/1e6:.0f}M",
        ]
        if analysis.get("tvl_usd"):
            lines.append(f"**TVL:** ${analysis['tvl_usd']/1e6:.0f}M")
        if analysis.get("apy_pct"):
            lines.append(f"**APY:** {analysis['apy_pct']}% (RWA yield)")
        lines.append("")
        lines.append("### Technical Signals")
        for sig in analysis["signal_summary"]:
            lines.append(f"• {sig}")
        lines.append("")
        lines.append(f"### ROI Projection (12 months)")
        lines.append(f"**Projected ROI:** {analysis['projected_roi_pct']:+.1f}%")
        lines.append(
            f"**Price Target:** ${analysis['price_target_12m']:.4f} "
            f"({'✅ Hits 20% target' if analysis['hits_roi_target'] else '⚠️ Below 20% target'})"
        )
        bd = analysis["roi_breakdown"]
        lines.append(f"• Momentum: {bd.get('momentum', 0):+.1f}%")
        if bd.get("apy"):
            lines.append(f"• APY yield: +{bd['apy']:.1f}%")
        if bd.get("tvl_bonus"):
            lines.append(f"• TVL bonus: +{bd['tvl_bonus']:.1f}%")
        if bd.get("mean_reversion"):
            lines.append(f"• Mean reversion: +{bd['mean_reversion']:.1f}%")
        lines.append("")
        lines.append(f"### Risk Assessment")
        lines.append(f"**Risk:** {analysis['risk_label']} ({analysis['risk_score']:.0f}/100)")
        lines.append(f"**Trust Score:** {analysis['trust_score']}/100")
        lines.append(f"**Sentiment:** Fear&Greed={analysis['fear_greed_value']}/100")
        lines.append("")
        reco_emoji = {
            "BUY": "✅", "ACCUMULATE": "📈", "WATCH": "👀",
            "HOLD": "⏸", "AVOID": "❌"
        }.get(analysis["recommendation"], "❓")
        lines.append(
            f"### {reco_emoji} Recommendation: {analysis['recommendation']}"
        )
        lines.append(analysis["recommendation_reason"])

        return {"result": "\n".join(lines)}

    except Exception as e:
        logger.error("[agent] token_info error: %s", e, exc_info=True)
        return {"result": f"Token analysis error: {e}"}


def market_status(state: AgentState) -> dict:
    """
    Quick market overview: Fear & Greed, top movers, sentiment.
    Triggered by: 'market status', 'how is the market', 'what's happening'
    """
    try:
        from data_pipeline import (
            get_all_tokens, get_latest_sentiment,
            get_all_sentiment_summary, get_data_freshness
        )

        tokens    = get_all_tokens()
        fg_row    = get_latest_sentiment("fear_greed", "MARKET")
        fg_details = fg_row.get("details_json", {}) if fg_row else {}
        fg_value  = fg_details.get("value", 50) if isinstance(fg_details, dict) else 50
        fg_label  = fg_row.get("label", "UNKNOWN") if fg_row else "UNKNOWN"
        freshness = get_data_freshness()

        # Fear & Greed emoji
        if fg_value >= 75:
            fg_emoji = "🟢 EXTREME GREED"
        elif fg_value >= 55:
            fg_emoji = "🟡 GREED"
        elif fg_value >= 45:
            fg_emoji = "⚪ NEUTRAL"
        elif fg_value >= 25:
            fg_emoji = "🟠 FEAR"
        else:
            fg_emoji = "🔴 EXTREME FEAR"

        lines = [
            f"## Market Status",
            f"",
            f"**Fear & Greed Index:** {fg_value}/100 — {fg_emoji}",
            f"**Data freshness:** {freshness['age_minutes']:.0f} min ago",
            f"",
        ]

        # Top gainers 24h
        with_change = [t for t in tokens if t.get("change_24h") is not None]
        gainers = sorted(with_change, key=lambda x: x["change_24h"], reverse=True)[:5]
        losers  = sorted(with_change, key=lambda x: x["change_24h"])[:3]

        lines.append("### Top Gainers (24h)")
        for t in gainers:
            lines.append(
                f"• **{t['symbol']}** {t['change_24h']:+.1f}%  "
                f"@ ${t['price_usd']:.4f}"
            )
        lines.append("")
        lines.append("### Top Losers (24h)")
        for t in losers:
            lines.append(
                f"• **{t['symbol']}** {t['change_24h']:+.1f}%  "
                f"@ ${t['price_usd']:.4f}"
            )
        lines.append("")

        # Sentiment sources
        sent = get_all_sentiment_summary()
        if sent:
            lines.append("### Sentiment Sources")
            for src, val in sent.items():
                icon = "🟢" if val["score"] > 0.6 else "🔴" if val["score"] < 0.4 else "⚪"
                lines.append(
                    f"• {icon} **{src.replace('_',' ').title()}**: "
                    f"{val['label']} ({val['score']:.2f})"
                )

        return {"result": "\n".join(lines)}

    except Exception as e:
        logger.error("[agent] market_status error: %s", e, exc_info=True)
        return {"result": f"Market status error: {e}"}


def verify_rwa(state: AgentState) -> dict:
    """
    Run full 5-check verification on a RWA token.
    Triggered by: 'verify ONDO', 'is ondo-finance legit', 'trust score for maple'
    """
    try:
        from verification_layer import verify_rwa_asset, get_trust_badge_emoji

        token_id = _extract_token_id(state.get("user_input", ""),
                                      state.get("token_id", ""))
        if not token_id:
            return {
                "result": (
                    "Which RWA token would you like me to verify? "
                    "Available: ondo-finance, centrifuge, maple, goldfinch, clearpool"
                )
            }

        report = verify_rwa_asset(token_id)

        if "error" in report:
            return {"result": f"Verification error: {report['error']}"}

        lines = [
            f"## RWA Trust Verification: {report['symbol']}",
            f"",
            f"**Trust Score:** {report['trust_score']}/100 — "
            f"{get_trust_badge_emoji(report['trust_score'])}",
            f"**Underlying:** {report['underlying']}",
            f"**Expected APY:** {report['expected_apy']}%",
            f"",
            f"### Score Breakdown",
        ]
        for check, vals in report["score_breakdown"].items():
            bar = "#" * vals["score"] + "." * (vals["max"] - vals["score"])
            lines.append(
                f"• **{check.replace('_',' ').title()}:** "
                f"[{bar}] {vals['score']}/{vals['max']}"
            )
        lines.append("")
        if report["proof_points"]:
            lines.append("### Proof Points")
            for p in report["proof_points"]:
                lines.append(f"✅ {p}")
            lines.append("")
        if report["risk_factors"]:
            lines.append("### Risk Factors")
            for r in report["risk_factors"][:5]:
                lines.append(f"⚠️ {r}")

        return {"result": "\n".join(lines)}

    except Exception as e:
        logger.error("[agent] verify_rwa error: %s", e, exc_info=True)
        return {"result": f"Verification error: {e}"}


# ═══════════════════════════════════════════════════════════════════════════════
# Routing Helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _extract_roi(text: str, default: float = 20.0) -> float:
    """Extract ROI percentage from user message."""
    import re
    matches = re.findall(r'(\d+(?:\.\d+)?)\s*%', text)
    if matches:
        return float(matches[0])
    return default


def _extract_budget(amount_str: str, default: float = 1000.0) -> float:
    """Extract budget from amount field or text."""
    import re
    if amount_str:
        try:
            return float(amount_str)
        except ValueError:
            pass
    return default


def _extract_token_id(text: str, hint: str = "") -> str:
    """
    Extract CoinGecko token ID from user message.
    Maps common names/symbols → CoinGecko IDs.
    """
    if hint:
        return hint.lower()

    text_lower = text.lower()

    # Symbol → CoinGecko ID map
    symbol_map = {
        "btc":     "bitcoin",        "bitcoin":  "bitcoin",
        "eth":     "ethereum",       "ethereum": "ethereum",
        "link":    "chainlink",      "chainlink":"chainlink",
        "aave":    "aave",
        "uni":     "uniswap",        "uniswap":  "uniswap",
        "mkr":     "maker",          "maker":    "maker",
        "crv":     "curve-dao-token","curve":    "curve-dao-token",
        "ldo":     "lido-dao",       "lido":     "lido-dao",
        "arb":     "arbitrum",       "arbitrum": "arbitrum",
        "op":      "optimism",       "optimism": "optimism",
        "ondo":    "ondo-finance",   "ondo-finance": "ondo-finance",
        "cfg":     "centrifuge",     "centrifuge":"centrifuge",
        "mpl":     "maple",          "maple":    "maple",
        "gfi":     "goldfinch",      "goldfinch":"goldfinch",
        "cpool":   "clearpool",      "clearpool":"clearpool",
        "pendle":  "pendle",
        "gmx":     "gmx",
        "gns":     "gains-network",
    }

    for kw, cg_id in symbol_map.items():
        if kw in text_lower:
            return cg_id

    return ""


# ═══════════════════════════════════════════════════════════════════════════════
# Router
# ═══════════════════════════════════════════════════════════════════════════════

def route_by_intent(state: AgentState) -> str:
    routing = {
        # Wallet ops (original)
        "check_user_balance":  "check_user_balance",
        "check_agent_balance": "check_agent_balance",
        "transfer_to_agent":   "transfer_to_agent",
        "create_wallet":       "create_wallet",
        # Trading intelligence (new)
        "analyze_market":      "analyze_market",
        "suggest_trades":      "suggest_trades",
        "token_info":          "token_info",
        "market_status":       "market_status",
        "verify_rwa":          "verify_rwa",
    }
    return routing.get(state.get("intent", "unknown"), "handle_unknown")


# ═══════════════════════════════════════════════════════════════════════════════
# Graph Builder
# ═══════════════════════════════════════════════════════════════════════════════

def build_graph():
    graph = StateGraph(AgentState)

    # Core nodes
    graph.add_node("parse_intent",        parse_intent)

    # Wallet nodes (original)
    graph.add_node("check_user_balance",  check_user_balance)
    graph.add_node("check_agent_balance", check_agent_balance)
    graph.add_node("transfer_to_agent",   transfer_to_agent)
    graph.add_node("create_wallet",       create_wallet)

    # Trading intelligence nodes (new)
    graph.add_node("analyze_market",      analyze_market)
    graph.add_node("suggest_trades",      suggest_trades)
    graph.add_node("token_info",          token_info)
    graph.add_node("market_status",       market_status)
    graph.add_node("verify_rwa",          verify_rwa)

    # Fallback
    graph.add_node("handle_unknown",      handle_unknown)

    # Entry point
    graph.set_entry_point("parse_intent")

    # All routing destinations
    all_nodes = {
        "check_user_balance":  "check_user_balance",
        "check_agent_balance": "check_agent_balance",
        "transfer_to_agent":   "transfer_to_agent",
        "create_wallet":       "create_wallet",
        "analyze_market":      "analyze_market",
        "suggest_trades":      "suggest_trades",
        "token_info":          "token_info",
        "market_status":       "market_status",
        "verify_rwa":          "verify_rwa",
        "handle_unknown":      "handle_unknown",
    }
    graph.add_conditional_edges("parse_intent", route_by_intent, all_nodes)

    # All nodes → END
    for node_name in all_nodes:
        graph.add_edge(node_name, END)

    return graph.compile()
