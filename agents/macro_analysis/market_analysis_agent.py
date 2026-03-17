"""
market_analysis_agent.py — Market Analysis Sub-Agent
=====================================================
Analyzes current market conditions using LIVE data:
price trends, volatility, correlations, sentiment, market regime.

Data Sources:
  - CoinGecko           → live token prices, market caps, changes
  - Alternative.me       → Fear & Greed Index (live)
  - DeFiLlama           → DeFi TVL, RWA protocol data
  - CoinGecko Global    → total market cap, BTC dominance

Input:  customer_risk_profile dict
Output: market_analysis dict with market regime, sentiment, and signals
"""

import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

from .data_pipeline import (
    fetch_token_prices,
    fetch_rwa_category_tokens,
    fetch_global_market_data,
    fetch_fear_greed,
    fetch_defi_tvl,
    fetch_defi_stablecoins,
    fetch_gecko_terminal_trending,
    fetch_gdelt_events,
    fetch_alpha_vantage_news,
    fetch_reddit_sentiment,
)

logger = logging.getLogger(__name__)

# RWA token IDs for sector-specific analysis
RWA_TOKEN_IDS = {
    "ondo-finance", "centrifuge", "maple-finance", "goldfinch",
    "clearpool", "pendle",
}


# ═══════════════════════════════════════════════════════════════════════════════
# Market Regime Detection (from live data)
# ═══════════════════════════════════════════════════════════════════════════════

def _detect_market_regime(
    fear_greed_value: int,
    btc_30d_change: float,
    avg_volatility: float,
) -> Dict[str, Any]:
    """Detect market regime from live indicators."""
    if fear_greed_value >= 80 and btc_30d_change > 15:
        regime = "EUPHORIA"
        desc = "Extreme greed with strong momentum — caution advised"
        confidence = 0.85
    elif fear_greed_value >= 55 and btc_30d_change > 5:
        regime = "RISK_ON"
        desc = "Bullish sentiment with positive trends — favorable for growth"
        confidence = 0.75
    elif fear_greed_value <= 20 and btc_30d_change < -15:
        regime = "CAPITULATION"
        desc = "Extreme fear with sharp declines — potential accumulation"
        confidence = 0.80
    elif fear_greed_value <= 35 and btc_30d_change < 0:
        regime = "RISK_OFF"
        desc = "Defensive sentiment — favor stable yield-bearing RWAs"
        confidence = 0.70
    else:
        regime = "NEUTRAL"
        desc = "Mixed signals — balanced allocation recommended"
        confidence = 0.60

    return {
        "regime": regime,
        "description": desc,
        "confidence": confidence,
        "signals": {
            "fear_greed": fear_greed_value,
            "btc_30d_change": btc_30d_change,
            "avg_volatility": round(avg_volatility, 3),
        },
    }


def _compute_momentum(token: Dict) -> float:
    """Compute momentum score for a token from live price changes."""
    return (
        (token.get("change_24h_pct", 0) or 0) * 0.2 +
        (token.get("change_7d_pct", 0) or 0) * 0.3 +
        (token.get("change_30d_pct", 0) or 0) * 0.5
    )


def _classify_trend(momentum: float) -> str:
    """Classify trend from momentum score."""
    if momentum > 10:
        return "STRONG_UP"
    elif momentum > 3:
        return "UP"
    elif momentum > -3:
        return "SIDEWAYS"
    elif momentum > -10:
        return "DOWN"
    return "STRONG_DOWN"


def _estimate_volatility(token: Dict) -> float:
    """
    Estimate volatility from price change magnitudes.
    (In production, use historical price data for proper std dev calculation)
    """
    changes = [
        abs(token.get("change_24h_pct", 0) or 0),
        abs(token.get("change_7d_pct", 0) or 0) / 2.65,  # scale to daily
        abs(token.get("change_30d_pct", 0) or 0) / 5.48,  # scale to daily
    ]
    avg_daily_change = sum(changes) / len(changes)
    # Annualize: daily_vol * sqrt(365)
    return round(avg_daily_change * 19.1 / 100, 3)  # sqrt(365) ≈ 19.1


# ═══════════════════════════════════════════════════════════════════════════════
# Main Agent Function
# ═══════════════════════════════════════════════════════════════════════════════

def run_market_analysis(customer_risk_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run comprehensive market analysis using LIVE data.
    """
    try:
        profile = customer_risk_profile or {}
        risk_tolerance = profile.get("risk_tolerance", "moderate")

        # Fetch live data
        tokens = fetch_token_prices()
        fear_greed = fetch_fear_greed()
        defi_tvl = fetch_defi_tvl()
        rwa_tokens = fetch_rwa_category_tokens()
        global_market = fetch_global_market_data()
        gdelt = fetch_gdelt_events("crypto OR blockchain OR tokenized")
        av_news = fetch_alpha_vantage_news()
        reddit = fetch_reddit_sentiment()
        gt_pools = fetch_gecko_terminal_trending()
        stablecoins = fetch_defi_stablecoins()

        if not tokens:
            return {
                "error": "Could not fetch token data from CoinGecko",
                "market_regime": {"regime": "UNKNOWN"},
                "data_source": "ERROR",
            }

        # Fear & Greed
        fg_value = fear_greed.get("value", 50)

        # Build token-level analysis
        token_map = {t["id"]: t for t in tokens}
        btc = token_map.get("bitcoin", {})
        btc_30d = btc.get("change_30d_pct", 0) or 0

        # Compute momentum signals
        momentum_signals = []
        volatilities = []
        for token in tokens:
            momentum = _compute_momentum(token)
            vol = _estimate_volatility(token)
            volatilities.append(vol)

            vol_ratio = (token.get("volume_24h_usd", 0) or 0) / max(token.get("market_cap_usd", 1), 1)
            volume_signal = "HIGH" if vol_ratio > 0.05 else "NORMAL" if vol_ratio > 0.01 else "LOW"

            momentum_signals.append({
                "token_id": token.get("id"),
                "symbol": token.get("symbol"),
                "price_usd": token.get("price_usd", 0),
                "momentum_score": round(momentum, 2),
                "trend": _classify_trend(momentum),
                "volatility_est": vol,
                "volume_signal": volume_signal,
                "changes": {
                    "24h": round(token.get("change_24h_pct", 0) or 0, 2),
                    "7d": round(token.get("change_7d_pct", 0) or 0, 2),
                    "30d": round(token.get("change_30d_pct", 0) or 0, 2),
                },
                "market_cap_usd": token.get("market_cap_usd", 0),
            })

        momentum_signals.sort(key=lambda x: x["momentum_score"], reverse=True)
        avg_volatility = sum(volatilities) / max(len(volatilities), 1)

        # Market regime
        market_regime = _detect_market_regime(fg_value, btc_30d, avg_volatility)

        # Top gainers/losers
        top_gainers = [s for s in momentum_signals if s["momentum_score"] > 0][:5]
        top_losers = list(reversed([s for s in momentum_signals if s["momentum_score"] <= 0]))[:3]

        # Volatility summary
        vol_regime = "HIGH" if avg_volatility > 0.6 else "MODERATE" if avg_volatility > 0.3 else "LOW"
        volatility_summary = {
            "average_est": round(avg_volatility, 3),
            "volatility_regime": vol_regime,
        }

        # RWA sector momentum from live RWA tokens
        rwa_momentums = []
        for token in rwa_tokens:
            m = _compute_momentum(token)
            rwa_momentums.append(m)
        rwa_avg_momentum = sum(rwa_momentums) / max(len(rwa_momentums), 1) if rwa_momentums else 0

        rwa_tvl = sum(
            chain_tvl for chain_tvl in (defi_tvl.get("top_chains", {}).values())
        )

        rwa_sector = {
            "avg_momentum": round(rwa_avg_momentum, 2),
            "trend": "UP" if rwa_avg_momentum > 3 else "SIDEWAYS" if rwa_avg_momentum > -3 else "DOWN",
            "tokens_tracked": len(rwa_tokens),
        }

        # Investment signals
        investment_signals = []
        if market_regime["regime"] == "RISK_OFF":
            investment_signals.append({
                "signal": "DEFENSIVE",
                "message": "Risk-off — prioritize treasury-backed and yield-bearing RWAs",
                "strength": "STRONG",
            })
        elif market_regime["regime"] == "RISK_ON":
            investment_signals.append({
                "signal": "GROWTH",
                "message": "Risk-on — growth-oriented RWAs and DeFi yield favorable",
                "strength": "MODERATE",
            })
        if rwa_sector["trend"] == "UP":
            investment_signals.append({
                "signal": "RWA_BULLISH",
                "message": f"RWA sector momentum positive ({rwa_avg_momentum:+.1f})",
                "strength": "STRONG",
            })
        if vol_regime == "HIGH":
            investment_signals.append({
                "signal": "HIGH_VOLATILITY",
                "message": "Elevated volatility — reduce position sizes or hedge",
                "strength": "MODERATE",
            })

        # Volatility/momentum bias
        vol_tolerance = {"conservative": "LOW", "moderate": "MEDIUM", "aggressive": "HIGH"}.get(risk_tolerance, "MEDIUM")
        momentum_bias = "GROWTH" if market_regime["regime"] in ("RISK_ON", "EUPHORIA") else "DEFENSIVE" if market_regime["regime"] in ("RISK_OFF", "CAPITULATION") else "BALANCED"

        result = {
            "market_regime": market_regime,
            "fear_greed": fear_greed,
            "momentum_signals": momentum_signals,
            "top_gainers": top_gainers,
            "top_losers": top_losers,
            "volatility_summary": volatility_summary,
            "volatility_tolerance": vol_tolerance,
            "momentum_bias": momentum_bias,
            "rwa_sector_momentum": rwa_sector,
            "global_market": global_market,
            "defi_tvl": defi_tvl,
            "investment_signals": investment_signals,
            "tokens_analyzed": len(tokens),
            "rwa_tokens_analyzed": len(rwa_tokens),
            "stablecoin_market": stablecoins,
            "gecko_terminal_pools": gt_pools[:5],
            "gdelt_news": {"count": gdelt.get("count", 0), "headlines": [a["title"] for a in gdelt.get("articles", [])[:3]]},
            "alpha_vantage_news": {"count": av_news.get("count", 0), "articles": av_news.get("articles", [])[:3]},
            "reddit": {"count": reddit.get("count", 0), "top_posts": [p["title"] for p in reddit.get("posts", [])[:3]]},
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "data_source": "LIVE (CoinGecko + Alternative.me + DeFiLlama + GDELT + Reddit + GeckoTerminal)",
        }

        logger.info(
            "[MarketAgent] Regime=%s | F&G=%d | RWA_Mom=%.1f | Vol=%s",
            market_regime["regime"], fg_value, rwa_avg_momentum, vol_regime,
        )
        return result

    except Exception as e:
        logger.error("[MarketAgent] Error: %s", e, exc_info=True)
        return {
            "error": str(e),
            "market_regime": {"regime": "UNKNOWN"},
            "fear_greed": {},
            "momentum_signals": [],
            "investment_signals": [],
            "data_source": "ERROR",
        }
