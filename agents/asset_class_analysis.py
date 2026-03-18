"""
Asset Class Analysis Agent
===========================
Performs cross-asset correlation analysis, anti-correlation detection,
R-squared computation, and diversification scoring on the matched assets.

Uses price history data to compute statistical relationships between
asset pairs, helping optimize portfolio construction.
"""

import logging
import math
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from state import MultiAgentState
from data_sources import fetch_coingecko_price_history

logger = logging.getLogger(__name__)


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

    # Fetch price histories in parallel
    price_histories = {}
    return_series = {}
    volatilities = {}
    with ThreadPoolExecutor(max_workers=len(gecko_ids) or 1) as pool:
        futures = {gid: pool.submit(fetch_coingecko_price_history, gid, 90) for gid in gecko_ids}
    for gid, fut in futures.items():
        prices_raw = fut.result()
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

    # Rule-based diversification assessment
    if div_score >= 65:
        assessment = "WELL_DIVERSIFIED"
    elif div_score >= 40:
        assessment = "MODERATE"
    else:
        assessment = "CONCENTRATED"

    # Identify concentration risks from asset types
    type_counts: dict = {}
    for a in top_assets:
        t = a.get("asset_type", "other")
        type_counts[t] = type_counts.get(t, 0) + 1
    concentration_risks = [
        f"High concentration in {t} ({n} assets)"
        for t, n in type_counts.items() if n >= 3
    ]
    if high_correlations:
        concentration_risks.append(f"{len(high_correlations)} asset pairs are highly correlated (>0.7)")

    # Build recommended mix from match scores and volatilities
    total_score = sum(a.get("match_score", 50) for a in top_assets) or 1
    recommended_mix = [
        {
            "slug": a.get("slug"),
            "symbol": a.get("symbol"),
            "allocation_pct": round(a.get("match_score", 50) / total_score * 100, 1),
        }
        for a in top_assets
    ]

    analysis = {
        "diversification_score": div_score,
        "diversification_assessment": assessment,
        "anti_correlations": anti_correlations,
        "high_correlations": high_correlations,
        "concentration_risks": concentration_risks,
        "recommended_mix": recommended_mix,
        "_raw_stats": {
            "correlations": correlations,
            "r_squared": r_squared_map,
            "volatilities": volatilities,
        },
    }

    logger.info(
        "[asset_class_analysis] Done: div_score=%s pairs=%d anti_corr=%d",
        div_score, len(correlations), len(anti_correlations),
    )

    return {"asset_class_analysis": analysis}
