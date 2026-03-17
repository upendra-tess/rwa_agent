"""
agent_graph.py — LangGraph Agent State Machine
================================================
Routes through the RWA Agent pipeline:

  Customer Risk Profiling → Macro Analysis → [Match Asset → ...]

Nodes:
  customer_risk_profiling  → builds risk profile from user input
  macro_analysis           → runs all 5 sub-agents (industry, financial,
                             cash flow, geopolitical, market)

Future nodes (not yet implemented):
  match_asset              → matches profile + macro to specific assets
  asset_class_analysis     → deep-dive into selected asset classes
  asset_analysis           → individual asset evaluation
"""

import logging
import json
from langgraph.graph import StateGraph, END

from state import AgentState
from agents.macro_analysis import run_macro_analysis

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Node: Customer Risk Profiling (placeholder — already built by team)
# ═══════════════════════════════════════════════════════════════════════════════

def customer_risk_profiling(state: AgentState) -> dict:
    """
    Build a customer risk profile from user input.

    In production, this would:
    - Parse user's investment goals, risk appetite, budget, etc.
    - Use LLM to classify risk tolerance
    - Pull KYC/jurisdiction data

    For now, returns a default moderate profile that downstream agents can use.
    """
    user_input = state.get("user_input", "")

    # Simple heuristic extraction (replace with LLM-based parsing)
    profile = {
        "risk_tolerance": "moderate",
        "investment_horizon": "medium",
        "target_roi_pct": 15.0,
        "budget_usd": 10000.0,
        "preferred_asset_types": ["RWA", "TokenizedTreasury"],
        "jurisdiction": "US",
        "kyc_status": "verified",
    }

    # Basic keyword detection for risk tolerance
    lower_input = user_input.lower()
    if any(w in lower_input for w in ["conservative", "safe", "low risk", "stable"]):
        profile["risk_tolerance"] = "conservative"
        profile["target_roi_pct"] = 8.0
    elif any(w in lower_input for w in ["aggressive", "high risk", "maximum", "growth"]):
        profile["risk_tolerance"] = "aggressive"
        profile["target_roi_pct"] = 25.0

    # Budget extraction
    import re
    budget_match = re.search(r'\$?([\d,]+(?:\.\d+)?)\s*(?:k|K|usd|USD)?', user_input)
    if budget_match:
        try:
            budget_str = budget_match.group(1).replace(",", "")
            budget = float(budget_str)
            if budget < 100:
                budget *= 1000  # assume "k"
            profile["budget_usd"] = budget
        except ValueError:
            pass

    logger.info(
        "[RiskProfiling] Tolerance=%s | ROI=%.0f%% | Budget=$%.0f",
        profile["risk_tolerance"], profile["target_roi_pct"], profile["budget_usd"],
    )

    return {"customer_risk_profile": profile}


# ═══════════════════════════════════════════════════════════════════════════════
# Node: Macro Analysis (orchestrates 5 sub-agents)
# ═══════════════════════════════════════════════════════════════════════════════

def macro_analysis(state: AgentState) -> dict:
    """
    Run the Macro Analysis Agent which orchestrates:
    - Industry Analysis Agent
    - Financial Analysis Agent
    - Cash Flow Agent
    - Geopolitical Analysis Agent
    - Market Analysis Agent

    Takes customer_risk_profile from previous node and produces
    a comprehensive macro_analysis_report.
    """
    profile = state.get("customer_risk_profile", {})

    try:
        report = run_macro_analysis(customer_risk_profile=profile)

        # Format summary for chat output
        summary = report.get("summary", "Macro analysis complete.")
        score = report.get("overall_macro_score", 0)
        assets = report.get("recommended_asset_types", [])

        result_text = (
            f"## Macro Analysis Report\n\n"
            f"**Overall Macro Score:** {score}/100\n\n"
            f"{summary}\n\n"
            f"**Recommended Asset Types:** {', '.join(assets) if assets else 'N/A'}\n\n"
            f"*{report.get('agents_completed', '0/5')} sub-agents completed successfully*"
        )

        return {
            "macro_analysis_report": report,
            "industry_analysis": report.get("industry_analysis"),
            "financial_analysis": report.get("financial_analysis"),
            "cash_flow_analysis": report.get("cash_flow_analysis"),
            "geopolitical_analysis": report.get("geopolitical_analysis"),
            "market_analysis": report.get("market_analysis"),
            "result": result_text,
        }

    except Exception as e:
        logger.error("[MacroNode] Error: %s", e, exc_info=True)
        return {
            "macro_analysis_report": {"error": str(e)},
            "result": f"Macro analysis error: {e}",
            "error": str(e),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# Graph Builder
# ═══════════════════════════════════════════════════════════════════════════════

def build_graph():
    """
    Build and compile the LangGraph state machine.

    Current flow:
      customer_risk_profiling → macro_analysis → END

    Future flow (when more agents are added):
      customer_risk_profiling → macro_analysis → match_asset
        → asset_class_analysis → asset_analysis → END
    """
    graph = StateGraph(AgentState)

    # ── Add nodes ───────────────────────────────────────────────────────
    graph.add_node("customer_risk_profiling", customer_risk_profiling)
    graph.add_node("macro_analysis", macro_analysis)

    # ── Set entry point ─────────────────────────────────────────────────
    graph.set_entry_point("customer_risk_profiling")

    # ── Define edges ────────────────────────────────────────────────────
    graph.add_edge("customer_risk_profiling", "macro_analysis")
    graph.add_edge("macro_analysis", END)

    return graph.compile()
