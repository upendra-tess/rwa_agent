"""
Match Asset Agent
==================
Receives the 5 parallel analysis results + customer profile and identifies
the best-fitting RWA assets from the LIVE RWA universe (sourced from DefiLlama).

Combines fundamental analysis scores into a unified asset ranking,
then filters and ranks based on customer-specific constraints.
"""

import json
import logging

from bedrock_client import BedrockClient
from state import MultiAgentState

logger = logging.getLogger(__name__)
bedrock = BedrockClient()

# Redemption window compatibility
REDEMPTION_ORDER = ["daily", "weekly", "monthly", "quarterly", "locked"]

# Asset type -> risk category mapping
ASSET_TYPE_RISK = {
    "treasury": "conservative",
    "gold": "conservative",
    "stablecoin_rwa": "conservative",
    "credit": "moderate",
    "real_estate": "moderate",
    "insurance": "moderate",
    "equity": "aggressive",
    "yield": "aggressive",
    "commodity": "moderate",
    "other": "moderate",
}

# Asset type -> estimated redemption window
ASSET_TYPE_REDEMPTION = {
    "treasury": "daily",
    "gold": "daily",
    "stablecoin_rwa": "daily",
    "credit": "monthly",
    "real_estate": "quarterly",
    "insurance": "quarterly",
    "equity": "daily",
    "yield": "weekly",
    "commodity": "weekly",
    "other": "monthly",
}

MATCH_SYSTEM_PROMPT = """You are a Match Asset Agent for an RWA tokenization investment platform.

You are given:
- A customer profile (budget, region, time horizon, expected return, redemption needs, risk tolerance)
- Analysis results from industry, financial, cash flow, geopolitical, and market agents
- The LIVE RWA asset universe (real protocols with real TVL data from DefiLlama)

Your job is to RANK the top 10-15 best-fitting assets for this specific customer from the universe provided.

For each asset, compute a match_score (0-100) based on:
- RETURN FIT (25%): Does the asset type's typical yield meet the customer's return target?
- RISK FIT (25%): Does the asset's risk profile match the customer's risk tolerance?
- REDEMPTION FIT (15%): Can the customer access liquidity within their desired window?
- SIZE/TRUST FIT (15%): Higher TVL = more trusted, audited = safer
- MACRO FIT (10%): Is the macro environment favorable for this asset type?
- MARKET FIT (10%): Is market sentiment positive for this asset?

Return ONLY valid JSON - a list of matched assets sorted by match_score descending:
[
  {
    "slug": "<string>",
    "name": "<string>",
    "symbol": "<string>",
    "asset_type": "<string>",
    "tvl": <float>,
    "chain": "<string>",
    "match_score": <0-100>,
    "match_breakdown": {
      "return_fit": <0-25>,
      "risk_fit": <0-25>,
      "redemption_fit": <0-15>,
      "size_trust_fit": <0-15>,
      "macro_fit": <0-10>,
      "market_fit": <0-10>
    },
    "estimated_apy_range": "<string e.g. '4-6%'>",
    "match_reason": "<string>",
    "suggested_allocation_pct": <float>,
    "warnings": [<strings>]
  }
]"""


def match_asset_agent(state: MultiAgentState) -> dict:
    """Match assets from live RWA universe to customer profile."""
    logger.info("[match_asset] Starting asset matching...")

    customer = state.get("customer_profile", {})
    macro = state.get("macro_context", {})
    rwa_universe = state.get("rwa_universe", [])
    industry = state.get("industry_analysis", {})
    financial = state.get("financial_analysis", {})
    cashflow = state.get("cashflow_analysis", {})
    geopolitical = state.get("geopolitical_analysis", {})
    market = state.get("market_analysis", {})

    if not rwa_universe:
        logger.warning("[match_asset] RWA universe is empty")
        return {"matched_assets": []}

    # Build condensed analysis summary
    analysis_summary = {
        "industry": {
            "score": industry.get("overall_score", 50),
            "outlook": industry.get("overall_outlook", "NEUTRAL"),
        },
        "financial": {
            "score": financial.get("overall_score", 50),
            "assessment": financial.get("overall_assessment", "NEUTRAL"),
        },
        "cashflow": {
            "score": cashflow.get("overall_score", 50),
            "assessment": cashflow.get("overall_assessment", "ADEQUATE"),
        },
        "geopolitical": {
            "score": geopolitical.get("overall_score", 50),
            "risk_level": geopolitical.get("overall_risk_level", "MEDIUM"),
        },
        "market": {
            "score": market.get("overall_score", 50),
            "sentiment": market.get("overall_sentiment", "NEUTRAL"),
        },
    }

    # Send top 40 RWA protocols to LLM for matching (avoid token overflow)
    universe_for_llm = [
        {
            "slug": a["slug"], "name": a["name"], "symbol": a["symbol"],
            "tvl": a["tvl"], "chain": a["chain"], "asset_type": a["asset_type"],
            "audits": a.get("audits", 0), "chains": a.get("chains", []),
            "change_7d": a.get("change_7d"),
            "gecko_id": a.get("gecko_id", ""),
        }
        for a in rwa_universe[:40]
    ]

    data_context = {
        "customer_profile": customer,
        "macro_context": {
            "regime": macro.get("macro_regime", "UNKNOWN"),
            "rate_env": macro.get("rate_environment", "UNKNOWN"),
            "rwa_attractiveness": macro.get("rwa_attractiveness_label", "NEUTRAL"),
            "rwa_score": macro.get("rwa_attractiveness_score", 50),
        },
        "analysis_summary": analysis_summary,
        "rwa_universe": universe_for_llm,
    }

    prompt = (
        "Match the best RWA assets for this customer from the live universe:\n\n"
        f"{json.dumps(data_context, indent=2, default=str)}"
    )

    raw = bedrock.send_message(prompt, system_prompt=MATCH_SYSTEM_PROMPT)

    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        matched = json.loads(text)
        if not isinstance(matched, list):
            matched = [matched]
    except json.JSONDecodeError:
        logger.warning("[match_asset] LLM parse failed, using rule-based fallback")
        matched = _rule_based_matching(rwa_universe, customer, macro)

    matched.sort(key=lambda x: x.get("match_score", 0), reverse=True)

    logger.info(
        "[match_asset] Matched %d assets. Top: %s (score=%s)",
        len(matched),
        matched[0].get("name") if matched else "none",
        matched[0].get("match_score") if matched else 0,
    )

    return {"matched_assets": matched}


def _rule_based_matching(rwa_universe: list, customer: dict, macro: dict) -> list:
    """Fallback rule-based matching if LLM parsing fails."""
    budget = customer.get("budget", 10000)
    target_return = customer.get("expected_return_pct", 10)
    risk_tol = customer.get("risk_tolerance", "moderate")
    redemption = customer.get("redemption_window", "monthly")
    redemption_idx = REDEMPTION_ORDER.index(redemption) if redemption in REDEMPTION_ORDER else 2

    # Estimated APY by asset type
    apy_estimates = {
        "treasury": 4.5, "gold": 0, "stablecoin_rwa": 5.0,
        "credit": 8.0, "real_estate": 7.0, "insurance": 6.0,
        "equity": 3.0, "yield": 10.0, "commodity": 2.0, "other": 5.0,
    }

    results = []
    for asset in rwa_universe[:40]:
        asset_type = asset.get("asset_type", "other")
        asset_risk = ASSET_TYPE_RISK.get(asset_type, "moderate")
        asset_redeem = ASSET_TYPE_REDEMPTION.get(asset_type, "monthly")
        est_apy = apy_estimates.get(asset_type, 5.0)
        score = 0

        # Return fit (0-25)
        if est_apy >= target_return:
            score += 25
        elif est_apy >= target_return * 0.7:
            score += 18
        else:
            score += max(0, int(10 * est_apy / max(target_return, 1)))

        # Risk fit (0-25)
        risk_match = {
            ("conservative", "conservative"): 25,
            ("conservative", "moderate"): 10,
            ("moderate", "moderate"): 25,
            ("moderate", "conservative"): 20,
            ("moderate", "aggressive"): 12,
            ("aggressive", "aggressive"): 25,
            ("aggressive", "moderate"): 18,
        }
        score += risk_match.get((risk_tol, asset_risk), 8)

        # Redemption fit (0-15)
        asset_redeem_idx = REDEMPTION_ORDER.index(asset_redeem) if asset_redeem in REDEMPTION_ORDER else 2
        if asset_redeem_idx <= redemption_idx:
            score += 15
        elif asset_redeem_idx == redemption_idx + 1:
            score += 8
        else:
            score += 3

        # Size/trust fit (0-15)
        tvl = asset.get("tvl", 0)
        if tvl >= 500_000_000:
            score += 15
        elif tvl >= 100_000_000:
            score += 12
        elif tvl >= 10_000_000:
            score += 8
        else:
            score += 4

        # Macro fit (0-10)
        rwa_score = macro.get("rwa_attractiveness_score", 50)
        score += min(10, int(rwa_score / 10))

        # Market fit (0-10) - neutral
        score += 5

        results.append({
            "slug": asset.get("slug", ""),
            "name": asset.get("name", ""),
            "symbol": asset.get("symbol", ""),
            "asset_type": asset_type,
            "tvl": tvl,
            "chain": asset.get("chain", ""),
            "gecko_id": asset.get("gecko_id", ""),
            "match_score": min(100, score),
            "match_breakdown": {},
            "estimated_apy_range": f"{est_apy:.0f}%",
            "match_reason": f"{asset.get('name')}: {asset_type}, TVL ${tvl/1e6:.0f}M",
            "suggested_allocation_pct": 0,
            "warnings": [],
        })

    results.sort(key=lambda x: x["match_score"], reverse=True)

    # Assign allocation to top picks
    total_alloc = 0
    for i, r in enumerate(results[:8]):
        alloc = max(5, 30 - i * 5)
        r["suggested_allocation_pct"] = alloc
        total_alloc += alloc
    if total_alloc > 0:
        for r in results[:8]:
            r["suggested_allocation_pct"] = round(
                r["suggested_allocation_pct"] / total_alloc * 100, 1)

    return results[:15]
