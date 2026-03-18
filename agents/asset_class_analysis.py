"""
Asset Class Analysis Agent
===========================
Performs cross-asset correlation analysis, anti-correlation detection,
R-squared computation, and diversification scoring on the matched assets.

Uses price history data to compute statistical relationships between
asset pairs, helping optimize portfolio construction.
"""

import json
import logging
import math
from typing import Optional

from bedrock_client import BedrockClient
from state import MultiAgentState
from data_sources import fetch_coingecko_price_history

logger = logging.getLogger(__name__)
bedrock = BedrockClient()


def _compute_returns(prices: list) -> list:
    """Convert price series to daily return series."""
    if len(prices) < 2:
        return []
    return [
        (prices[i] - prices[i - 1]) / prices[i - 1]
        for i in range(1, len(prices))
        if prices[i - 1] != 0
    ]


def _pearson_correlation(x: list, y: list) -> Optional[float]:
    """Compute Pearson correlation between two return series."""
    n = min(len(x), len(y))
    if n < 5:
        return None
    x, y = x[:n], y[:n]
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n)) / n
    std_x = math.sqrt(sum((xi - mean_x) ** 2 for xi in x) / n)
    std_y = math.sqrt(sum((yi - mean_y) ** 2 for yi in y) / n)
    if std_x == 0 or std_y == 0:
        return None
    return round(cov / (std_x * std_y), 4)


def _r_squared(x: list, y: list) -> Optional[float]:
    """Compute R-squared between two return series."""
    corr = _pearson_correlation(x, y)
    if corr is None:
        return None
    return round(corr ** 2, 4)


def _compute_volatility(returns: list) -> float:
    """Annualized volatility from daily returns."""
    if len(returns) < 2:
        return 0.0
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    daily_vol = math.sqrt(variance)
    return round(daily_vol * math.sqrt(365) * 100, 2)  # annualized %


ANALYSIS_SYSTEM_PROMPT = """You are an Asset Class Analysis Agent specializing in portfolio optimization.

Given correlation/R-squared data between matched RWA assets, produce a diversification analysis:

1. CORRELATION_INSIGHTS: Which assets move together and which provide diversification
2. ANTI_CORRELATIONS: Asset pairs with negative correlation (diversification opportunities)
3. PORTFOLIO_CONSTRUCTION: How to weight assets for optimal diversification
4. CONCENTRATION_RISKS: If portfolio is too concentrated in correlated assets
5. RECOMMENDED_MIX: Optimal allocation percentages for diversification

Return ONLY valid JSON:
{
  "correlation_insights": [{"pair": "<A-B>", "correlation": <float>, "interpretation": "<string>"}],
  "anti_correlations": [{"pair": "<A-B>", "correlation": <float>, "benefit": "<string>"}],
  "high_correlations": [{"pair": "<A-B>", "correlation": <float>, "warning": "<string>"}],
  "diversification_score": <0-100>,
  "diversification_assessment": "<WELL_DIVERSIFIED|MODERATE|CONCENTRATED>",
  "concentration_risks": [<strings>],
  "recommended_mix": [{"token_id": "<string>", "symbol": "<string>", "allocation_pct": <float>, "reason": "<string>"}],
  "portfolio_metrics": {"expected_return": <float>, "expected_volatility": <float>, "sharpe_estimate": <float>},
  "summary": "<string>"
}"""


def asset_class_analysis_agent(state: MultiAgentState) -> dict:
    """Perform cross-asset correlation analysis on matched assets."""
    logger.info("[asset_class_analysis] Starting...")

    matched = state.get("matched_assets", [])
    customer = state.get("customer_profile", {})
    macro = state.get("macro_context", {})

    if not matched:
        logger.warning("[asset_class_analysis] No matched assets to analyze")
        return {"asset_class_analysis": {
            "diversification_score": 0,
            "summary": "No matched assets available for analysis",
        }}

    # Take top assets for correlation analysis
    top_assets = matched[:10]
    # Use gecko_id for price history (from live universe), fallback to slug
    gecko_ids = []
    slug_to_gecko = {}
    for a in top_assets:
        gid = a.get("gecko_id") or ""
        slug = a.get("slug", a.get("name", ""))
        if gid:
            gecko_ids.append(gid)
            slug_to_gecko[slug] = gid

    # Fetch price histories for assets with gecko_ids
    price_histories = {}
    return_series = {}
    volatilities = {}
    for gid in gecko_ids:
        prices_raw = fetch_coingecko_price_history(gid, days=90)
        if prices_raw:
            prices = [p[1] for p in prices_raw]
            price_histories[gid] = prices
            returns = _compute_returns(prices)
            return_series[gid] = returns
            volatilities[gid] = _compute_volatility(returns)

    # Compute pairwise correlations and R-squared
    correlations = {}
    r_squared_map = {}
    anti_correlations = []
    high_correlations = []

    tids_with_data = list(return_series.keys())
    for i in range(len(tids_with_data)):
        for j in range(i + 1, len(tids_with_data)):
            a, b = tids_with_data[i], tids_with_data[j]
            corr = _pearson_correlation(return_series[a], return_series[b])
            r2 = _r_squared(return_series[a], return_series[b])
            pair_key = f"{a}|{b}"
            if corr is not None:
                correlations[pair_key] = corr
                if corr < -0.1:
                    anti_correlations.append({
                        "pair": pair_key, "correlation": corr,
                    })
                elif corr > 0.7:
                    high_correlations.append({
                        "pair": pair_key, "correlation": corr,
                    })
            if r2 is not None:
                r_squared_map[pair_key] = r2

    # Compute diversification score
    if correlations:
        avg_corr = sum(abs(v) for v in correlations.values()) / len(correlations)
        div_score = max(0, min(100, int(100 * (1 - avg_corr))))
    else:
        div_score = 50

    # Build context for LLM
    data_context = {
        "customer_profile": {
            "risk_tolerance": customer.get("risk_tolerance", "moderate"),
            "expected_return": customer.get("expected_return_pct", 10),
            "time_horizon_months": customer.get("time_horizon_months", 12),
        },
        "matched_assets": [
            {
                "slug": a.get("slug"), "name": a.get("name"),
                "symbol": a.get("symbol"), "asset_type": a.get("asset_type"),
                "tvl": a.get("tvl"), "match_score": a.get("match_score"),
                "estimated_apy_range": a.get("estimated_apy_range", ""),
                "suggested_allocation": a.get("suggested_allocation_pct"),
                "volatility_annual_pct": volatilities.get(a.get("gecko_id", ""), 0),
            }
            for a in top_assets
        ],
        "correlations": correlations,
        "r_squared": r_squared_map,
        "anti_correlations": anti_correlations,
        "high_correlations": high_correlations,
        "diversification_score": div_score,
        "macro_regime": macro.get("macro_regime", "UNKNOWN"),
        "risk_free_rate": macro.get("key_rates", {}).get("yield_3m", 4.0),
    }

    prompt = (
        "Analyze the cross-asset correlations and recommend optimal portfolio diversification:\n\n"
        f"{json.dumps(data_context, indent=2, default=str)}"
    )

    raw = bedrock.send_message(prompt, system_prompt=ANALYSIS_SYSTEM_PROMPT)

    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        analysis = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("[asset_class_analysis] Failed to parse LLM response")
        analysis = {
            "diversification_score": div_score,
            "diversification_assessment": "MODERATE",
            "correlation_insights": [],
            "anti_correlations": anti_correlations,
            "high_correlations": high_correlations,
            "concentration_risks": [],
            "recommended_mix": [],
            "portfolio_metrics": {},
            "summary": "Statistical analysis completed; LLM interpretation unavailable.",
        }

    # Always attach raw statistical data
    analysis["_raw_stats"] = {
        "correlations": correlations,
        "r_squared": r_squared_map,
        "volatilities": volatilities,
    }

    logger.info(
        "[asset_class_analysis] Done: div_score=%s pairs=%d anti_corr=%d",
        analysis.get("diversification_score", div_score),
        len(correlations), len(anti_correlations),
    )

    return {"asset_class_analysis": analysis}
