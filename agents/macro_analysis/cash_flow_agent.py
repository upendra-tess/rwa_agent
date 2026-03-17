"""
cash_flow_agent.py — Cash Flow Analysis Sub-Agent
===================================================
Analyzes yield opportunities, liquidity profiles, and cash flow
projections using LIVE data from DeFiLlama yields API.

Data Sources:
  - DeFiLlama Yields API  → real APY, TVL, pool data
  - DeFiLlama Protocols   → RWA protocol TVL, growth
  - CoinGecko             → token liquidity (volume/mcap ratio)

Input:  customer_risk_profile dict
Output: cash_flow_analysis dict with yield requirements and liquidity risk
"""

import logging
from typing import Dict, Any, Optional, List

from .data_pipeline import (
    fetch_yield_pools,
    fetch_rwa_protocols,
    fetch_fred_macro,
    fetch_world_bank,
    fetch_imf_indicators,
    fetch_comtrade_trade,
    fetch_token_prices,
    fetch_gecko_terminal_trending,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Liquidity & Risk Mapping
# ═══════════════════════════════════════════════════════════════════════════════

LIQUIDITY_PREFERENCE_MAP = {
    "conservative": "HIGH",
    "moderate": "MEDIUM",
    "aggressive": "LOW",
}

HORIZON_LOCKUP_MAP = {
    "short": 30,
    "medium": 90,
    "long": 365,
}

# Project → asset category mapping
PROJECT_CATEGORY_MAP = {
    "aave": "defi_lending",
    "compound": "defi_lending",
    "lido": "liquid_staking",
    "rocket-pool": "liquid_staking",
    "maker": "cdp",
    "ondo": "tokenized_treasury",
    "mountain-protocol": "tokenized_treasury",
    "backed": "tokenized_treasury",
    "maple": "private_credit",
    "goldfinch": "private_credit",
    "clearpool": "private_credit",
    "centrifuge": "real_estate_rwa",
    "pendle": "yield_trading",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Cash Flow Analysis from Live Data
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_yield_requirement(target_roi: float, risk_tolerance: str) -> float:
    """Determine minimum acceptable yield from ROI target."""
    yield_share = {
        "conservative": 0.80,
        "moderate": 0.60,
        "aggressive": 0.40,
    }
    return target_roi * yield_share.get(risk_tolerance, 0.60)


def _categorize_pool(pool: Dict) -> str:
    """Categorize a yield pool based on its project."""
    project = pool.get("project", "").lower()
    for keyword, category in PROJECT_CATEGORY_MAP.items():
        if keyword in project:
            return category
    if pool.get("stablecoin"):
        return "stablecoin_yield"
    return "other"


def _assess_pool_liquidity(pool: Dict) -> Dict[str, Any]:
    """Assess liquidity of a yield pool."""
    tvl = pool.get("tvl_usd", 0)

    if tvl >= 1e9:
        liquidity = "VERY_HIGH"
        risk = "VERY_LOW"
    elif tvl >= 100e6:
        liquidity = "HIGH"
        risk = "LOW"
    elif tvl >= 10e6:
        liquidity = "MEDIUM"
        risk = "MEDIUM"
    else:
        liquidity = "LOW"
        risk = "HIGH"

    return {
        "liquidity": liquidity,
        "risk": risk,
        "tvl_usd": tvl,
    }


def _score_pool(
    pool: Dict,
    min_yield: float,
    liquidity_pref: str,
) -> int:
    """Score a yield pool for cash flow suitability (0-100)."""
    score = 0
    apy = pool.get("apy", 0)
    tvl = pool.get("tvl_usd", 0)

    # Yield adequacy (0-40 pts)
    if apy >= min_yield:
        score += 40
    elif apy >= min_yield * 0.7:
        score += 25
    elif apy > 0:
        score += 10

    # TVL/Liquidity (0-30 pts)
    if tvl >= 1e9:
        tvl_score = 30
    elif tvl >= 100e6:
        tvl_score = 25
    elif tvl >= 10e6:
        tvl_score = 15
    else:
        tvl_score = 5

    # Adjust for liquidity preference
    if liquidity_pref == "HIGH" and tvl < 100e6:
        tvl_score = max(0, tvl_score - 10)
    score += tvl_score

    # Stablecoin bonus (0-15 pts) — lower risk
    if pool.get("stablecoin"):
        score += 15
    else:
        score += 5

    # Base APY vs reward APY (0-15 pts) — prefer organic yield
    base_apy = pool.get("apy_base", 0) or 0
    if base_apy > 0 and apy > 0:
        organic_ratio = base_apy / apy
        score += int(organic_ratio * 15)

    return min(100, max(0, score))


def _aggregate_by_category(scored_pools: List[Dict]) -> Dict[str, Dict]:
    """Aggregate pools by category."""
    categories = {}
    for pool in scored_pools:
        cat = pool.get("category", "other")
        if cat not in categories:
            categories[cat] = {
                "pool_count": 0,
                "total_tvl_usd": 0,
                "avg_apy": 0,
                "apys": [],
                "top_pools": [],
            }
        categories[cat]["pool_count"] += 1
        categories[cat]["total_tvl_usd"] += pool.get("tvl_usd", 0)
        categories[cat]["apys"].append(pool.get("apy", 0))
        if len(categories[cat]["top_pools"]) < 5:
            categories[cat]["top_pools"].append({
                "project": pool.get("project"),
                "symbol": pool.get("symbol"),
                "apy": pool.get("apy"),
                "tvl_usd": pool.get("tvl_usd"),
            })

    for cat, data in categories.items():
        if data["apys"]:
            data["avg_apy"] = round(sum(data["apys"]) / len(data["apys"]), 2)
        del data["apys"]

    return categories


# ═══════════════════════════════════════════════════════════════════════════════
# Main Agent Function
# ═══════════════════════════════════════════════════════════════════════════════

def run_cash_flow_analysis(customer_risk_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run cash flow analysis using LIVE yield data from DeFiLlama.
    """
    try:
        profile = customer_risk_profile or {}
        risk_tolerance = profile.get("risk_tolerance", "moderate")
        target_roi = profile.get("target_roi_pct", 15.0)
        budget = profile.get("budget_usd", 10000.0)
        horizon = profile.get("investment_horizon", "medium")

        # Derive requirements
        min_yield = _compute_yield_requirement(target_roi, risk_tolerance)
        liquidity_pref = LIQUIDITY_PREFERENCE_MAP.get(risk_tolerance, "MEDIUM")
        max_lockup = HORIZON_LOCKUP_MAP.get(horizon, 90)

        # Fetch live data
        yield_pools = fetch_yield_pools()
        rwa_protocols = fetch_rwa_protocols()

        if not yield_pools:
            return {
                "error": "Could not fetch yield data from DeFiLlama",
                "preferred_yield_min_pct": min_yield,
                "data_source": "ERROR",
            }

        # Score and categorize each pool
        scored_pools = []
        for pool in yield_pools:
            category = _categorize_pool(pool)
            score = _score_pool(pool, min_yield, liquidity_pref)
            liquidity = _assess_pool_liquidity(pool)

            scored_pools.append({
                "project": pool.get("project"),
                "symbol": pool.get("symbol"),
                "chain": pool.get("chain"),
                "apy": pool.get("apy", 0),
                "apy_base": pool.get("apy_base", 0),
                "apy_reward": pool.get("apy_reward", 0),
                "tvl_usd": pool.get("tvl_usd", 0),
                "stablecoin": pool.get("stablecoin", False),
                "category": category,
                "score": score,
                "liquidity": liquidity,
                "meets_yield_requirement": pool.get("apy", 0) >= min_yield,
            })

        # Sort by score
        scored_pools.sort(key=lambda x: x["score"], reverse=True)
        top_pools = scored_pools[:10]

        # Aggregate by category
        categories = _aggregate_by_category(scored_pools)

        # Project annual income from top pools
        num_top = min(len(top_pools), 5)
        per_pool_alloc = budget / max(num_top, 1)
        total_annual = 0.0
        income_projections = []
        for pool in top_pools[:num_top]:
            annual = per_pool_alloc * (pool["apy"] / 100)
            total_annual += annual
            income_projections.append({
                "project": pool["project"],
                "symbol": pool["symbol"],
                "allocation_usd": round(per_pool_alloc, 2),
                "apy": pool["apy"],
                "annual_income_usd": round(annual, 2),
                "monthly_income_usd": round(annual / 12, 2),
            })

        effective_yield = round((total_annual / budget) * 100, 2) if budget > 0 else 0

        # Stability rating from live data
        stablecoin_pools = [p for p in top_pools[:num_top] if p["stablecoin"]]
        stablecoin_ratio = len(stablecoin_pools) / max(num_top, 1)
        avg_tvl = sum(p["tvl_usd"] for p in top_pools[:num_top]) / max(num_top, 1)

        if stablecoin_ratio >= 0.6 and avg_tvl >= 500e6:
            stability = "VERY_HIGH"
        elif stablecoin_ratio >= 0.4 and avg_tvl >= 100e6:
            stability = "HIGH"
        elif avg_tvl >= 10e6:
            stability = "MEDIUM"
        else:
            stability = "LOW"

        result = {
            "preferred_yield_min_pct": round(min_yield, 2),
            "liquidity_preference": liquidity_pref,
            "max_lockup_days": max_lockup,
            "top_yield_pools": top_pools[:10],
            "top_yield_assets": [f"{p['project']} ({p['symbol']})" for p in top_pools[:5]],
            "yield_categories": categories,
            "pools_meeting_yield_req": sum(1 for p in scored_pools if p["meets_yield_requirement"]),
            "total_pools_analyzed": len(scored_pools),
            "projected_annual_income": {
                "per_pool": income_projections,
                "total_annual_usd": round(total_annual, 2),
                "total_monthly_usd": round(total_annual / 12, 2),
                "effective_yield_pct": effective_yield,
            },
            "cash_flow_stability_rating": stability,
            "rwa_protocols": [
                {"name": p["name"], "tvl_usd": p["tvl_usd"]}
                for p in rwa_protocols[:10]
            ],
            "data_source": "LIVE (DeFiLlama Yields API)",
        }

        logger.info(
            "[CashFlowAgent] MinYield=%.1f%% | EffYield=%.1f%% | Pools=%d | Stability=%s",
            min_yield, effective_yield, len(scored_pools), stability,
        )
        return result

    except Exception as e:
        logger.error("[CashFlowAgent] Error: %s", e, exc_info=True)
        return {
            "error": str(e),
            "preferred_yield_min_pct": 0,
            "top_yield_assets": [],
            "cash_flow_stability_rating": "UNKNOWN",
            "data_source": "ERROR",
        }
