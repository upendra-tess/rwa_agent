"""
macro_agent.py — Macro Analysis Orchestrator Agent
====================================================
Coordinates all 5 macro analysis sub-agents and aggregates their
results into a unified MacroAnalysisReport.

Flow (from flowchart):
  Customer Risk Profile
        ↓
  MacroAnalysisAgent (this file)
    ├── IndustryAnalysisAgent
    ├── FinancialAnalysisAgent
    ├── CashFlowAgent
    ├── GeopoliticalAnalysisAgent
    └── MarketAnalysisAgent
        ↓
  (aggregated MacroAnalysisReport)
        ↓
  Match Asset Agent (next stage)
"""

import logging
from typing import Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from .industry_analysis_agent import run_industry_analysis
from .financial_analysis_agent import run_financial_analysis
from .cash_flow_agent import run_cash_flow_analysis
from .geopolitical_analysis_agent import run_geopolitical_analysis
from .market_analysis_agent import run_market_analysis

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Sub-Agent Registry
# ═══════════════════════════════════════════════════════════════════════════════

SUB_AGENTS = {
    "industry_analysis": {
        "name": "Industry Analysis Agent",
        "function": run_industry_analysis,
        "description": "Sector growth, competitive landscape, moat analysis",
    },
    "financial_analysis": {
        "name": "Financial Analysis Agent",
        "function": run_financial_analysis,
        "description": "Interest rates, inflation, credit conditions, duration",
    },
    "cash_flow_analysis": {
        "name": "Cash Flow Agent",
        "function": run_cash_flow_analysis,
        "description": "Yield requirements, liquidity, cash flow projections",
    },
    "geopolitical_analysis": {
        "name": "Geopolitical Analysis Agent",
        "function": run_geopolitical_analysis,
        "description": "Regulatory risk, jurisdictions, sanctions, compliance",
    },
    "market_analysis": {
        "name": "Market Analysis Agent",
        "function": run_market_analysis,
        "description": "Price trends, volatility, sentiment, market regime",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# Aggregation Logic
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_overall_macro_score(results: Dict[str, Any]) -> int:
    """
    Compute an overall macro score (0-100) by weighting sub-agent scores.
    """
    weights = {
        "industry": 0.20,
        "financial": 0.25,
        "cash_flow": 0.20,
        "geopolitical": 0.15,
        "market": 0.20,
    }

    scores = {}

    # Industry score — average of sector scores
    industry = results.get("industry_analysis", {})
    sector_scores = industry.get("sector_scores", {})
    if sector_scores:
        scores["industry"] = sum(sector_scores.values()) / len(sector_scores)
    else:
        scores["industry"] = 50

    # Financial score
    financial = results.get("financial_analysis", {})
    scores["financial"] = financial.get("financial_environment_score", 50)

    # Cash flow score — average of asset scores
    cash_flow = results.get("cash_flow_analysis", {})
    cf_scores = cash_flow.get("asset_cash_flow_scores", {})
    if cf_scores:
        scores["cash_flow"] = sum(cf_scores.values()) / len(cf_scores)
    else:
        scores["cash_flow"] = 50

    # Geopolitical score — average jurisdiction score
    geopolitical = results.get("geopolitical_analysis", {})
    scores["geopolitical"] = geopolitical.get("regulatory_clarity_avg_score", 50)

    # Market score — based on regime + sentiment
    market = results.get("market_analysis", {})
    regime = market.get("market_regime", {}).get("regime", "NEUTRAL")
    regime_scores = {
        "RISK_ON": 75, "NEUTRAL": 55, "RISK_OFF": 35,
        "EUPHORIA": 60, "CAPITULATION": 30,
    }
    scores["market"] = regime_scores.get(regime, 50)

    # Weighted average
    overall = sum(scores[k] * weights[k] for k in weights if k in scores)
    return max(0, min(100, int(overall)))


def _determine_recommended_asset_types(results: Dict[str, Any]) -> list:
    """
    Synthesize recommended asset types from all sub-agent outputs.
    """
    recommendations = set()

    # From industry analysis
    industry = results.get("industry_analysis", {})
    top_sector_ids = industry.get("top_sector_ids", [])
    sector_to_asset = {
        "treasury_yield": "TokenizedTreasury",
        "real_estate": "TokenizedRealEstate",
        "private_credit": "PrivateCredit",
        "commodities": "TokenizedCommodities",
        "infrastructure": "InfrastructureBonds",
        "equities": "TokenizedEquities",
        "defi_yield": "DeFiYield",
    }
    for sid in top_sector_ids:
        if sid in sector_to_asset:
            recommendations.add(sector_to_asset[sid])

    # From cash flow analysis
    cash_flow = results.get("cash_flow_analysis", {})
    top_yield = cash_flow.get("top_yield_assets", [])
    asset_name_map = {
        "Tokenized US Treasuries": "TokenizedTreasury",
        "Private Credit Pools": "PrivateCredit",
        "Tokenized Real Estate": "TokenizedRealEstate",
        "Tokenized Commodities": "TokenizedCommodities",
        "DeFi Yield Strategies": "DeFiYield",
        "Infrastructure Bonds": "InfrastructureBonds",
    }
    for name in top_yield:
        if name in asset_name_map:
            recommendations.add(asset_name_map[name])

    # From market analysis — if RWA sector is bullish, boost RWA types
    market = results.get("market_analysis", {})
    rwa_momentum = market.get("rwa_sector_momentum", {})
    if rwa_momentum.get("trend") == "UP":
        recommendations.add("TokenizedTreasury")
        recommendations.add("PrivateCredit")

    return sorted(list(recommendations))


def _generate_macro_summary(results: Dict[str, Any], overall_score: int) -> str:
    """Generate a human-readable summary of the macro analysis."""
    lines = []

    # Overall
    if overall_score >= 70:
        lines.append("🟢 **Macro environment is FAVORABLE** for RWA investment.")
    elif overall_score >= 50:
        lines.append("🟡 **Macro environment is NEUTRAL** — selective opportunities exist.")
    else:
        lines.append("🔴 **Macro environment is CHALLENGING** — proceed with caution.")

    # Industry
    industry = results.get("industry_analysis", {})
    if industry.get("top_sectors"):
        lines.append(f"**Top sectors:** {', '.join(industry['top_sectors'][:3])}")
        lines.append(f"**Growth outlook:** {industry.get('growth_outlook', 'N/A')}")

    # Financial
    financial = results.get("financial_analysis", {})
    lines.append(
        f"**Rates:** {financial.get('interest_rate_environment', 'N/A')} | "
        f"**Duration:** {financial.get('recommended_duration', 'N/A')}"
    )

    # Cash flow
    cash_flow = results.get("cash_flow_analysis", {})
    income = cash_flow.get("projected_annual_income", {})
    if income.get("effective_yield_pct"):
        lines.append(f"**Projected yield:** {income['effective_yield_pct']}% | "
                      f"**Stability:** {cash_flow.get('cash_flow_stability_rating', 'N/A')}")

    # Geopolitical
    geo = results.get("geopolitical_analysis", {})
    lines.append(f"**Geo risk:** {geo.get('geopolitical_risk_level', 'N/A')} | "
                  f"**Safe jurisdictions:** {', '.join(geo.get('safe_jurisdictions', [])[:3])}")

    # Market
    market = results.get("market_analysis", {})
    regime = market.get("market_regime", {})
    lines.append(f"**Market regime:** {regime.get('regime', 'N/A')} | "
                  f"**Momentum bias:** {market.get('momentum_bias', 'N/A')}")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Main Orchestrator Function
# ═══════════════════════════════════════════════════════════════════════════════

def run_macro_analysis(
    customer_risk_profile: Optional[Dict[str, Any]] = None,
    parallel: bool = True,
) -> Dict[str, Any]:
    """
    Run all 5 macro analysis sub-agents and aggregate results.

    Parameters
    ----------
    customer_risk_profile : dict
        Output from Customer Risk Profiling Agent.
    parallel : bool
        If True, run sub-agents in parallel threads.

    Returns
    -------
    dict — MacroAnalysisReport with keys:
        - industry_analysis
        - financial_analysis
        - cash_flow_analysis
        - geopolitical_analysis
        - market_analysis
        - overall_macro_score
        - recommended_asset_types
        - summary
        - sub_agent_status
    """
    logger.info("[MacroAgent] Starting macro analysis with %d sub-agents...",
                len(SUB_AGENTS))

    profile = customer_risk_profile or {}
    results = {}
    sub_agent_status = {}

    if parallel:
        # ── Run all sub-agents in parallel ──────────────────────────────
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {}
            for agent_id, agent_info in SUB_AGENTS.items():
                future = executor.submit(agent_info["function"], profile)
                futures[future] = agent_id

            for future in as_completed(futures):
                agent_id = futures[future]
                try:
                    result = future.result(timeout=30)
                    results[agent_id] = result
                    has_error = "error" in result
                    sub_agent_status[agent_id] = {
                        "status": "ERROR" if has_error else "SUCCESS",
                        "name": SUB_AGENTS[agent_id]["name"],
                    }
                    if has_error:
                        logger.warning("[MacroAgent] %s returned error: %s",
                                       agent_id, result.get("error"))
                    else:
                        logger.info("[MacroAgent] %s completed successfully", agent_id)
                except Exception as e:
                    logger.error("[MacroAgent] %s failed: %s", agent_id, e)
                    results[agent_id] = {"error": str(e)}
                    sub_agent_status[agent_id] = {
                        "status": "FAILED",
                        "name": SUB_AGENTS[agent_id]["name"],
                        "error": str(e),
                    }
    else:
        # ── Run sequentially ────────────────────────────────────────────
        for agent_id, agent_info in SUB_AGENTS.items():
            try:
                result = agent_info["function"](profile)
                results[agent_id] = result
                has_error = "error" in result
                sub_agent_status[agent_id] = {
                    "status": "ERROR" if has_error else "SUCCESS",
                    "name": agent_info["name"],
                }
            except Exception as e:
                logger.error("[MacroAgent] %s failed: %s", agent_id, e)
                results[agent_id] = {"error": str(e)}
                sub_agent_status[agent_id] = {
                    "status": "FAILED",
                    "name": agent_info["name"],
                    "error": str(e),
                }

    # ── Aggregate ───────────────────────────────────────────────────────
    overall_score = _compute_overall_macro_score(results)
    recommended_assets = _determine_recommended_asset_types(results)
    summary = _generate_macro_summary(results, overall_score)

    # Count successes
    success_count = sum(
        1 for s in sub_agent_status.values() if s["status"] == "SUCCESS"
    )

    macro_report = {
        "industry_analysis": results.get("industry_analysis", {}),
        "financial_analysis": results.get("financial_analysis", {}),
        "cash_flow_analysis": results.get("cash_flow_analysis", {}),
        "geopolitical_analysis": results.get("geopolitical_analysis", {}),
        "market_analysis": results.get("market_analysis", {}),
        "overall_macro_score": overall_score,
        "recommended_asset_types": recommended_assets,
        "summary": summary,
        "sub_agent_status": sub_agent_status,
        "agents_completed": f"{success_count}/{len(SUB_AGENTS)}",
        "analysis_timestamp": datetime.utcnow().isoformat(),
    }

    logger.info(
        "[MacroAgent] Complete | Score=%d | Assets=%s | Agents=%d/%d",
        overall_score,
        ", ".join(recommended_assets[:3]),
        success_count,
        len(SUB_AGENTS),
    )

    return macro_report
