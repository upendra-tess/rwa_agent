"""
trading_analyzer.py — Token Ranking & ROI Analysis Engine
==========================================================
Answers: "Given 50 tokens and a 20% ROI target, which should I buy?"

Pipeline:
  Step 1 — Feed:        Pull prices + TVL + sentiment + trust from data_pipeline / verification_layer
  Step 2 — Technicals:  RSI (14d) + MACD (12/26/9) + Bollinger Bands (20d)
  Step 3 — ROI Proj:    Momentum × 12 + APY (RWA) + TVL growth bonus
  Step 4 — Risk Score:  Volatility + market_cap + trust_score + sentiment
  Step 5 — Rank:        Composite score → sorted Top-N list with buy targets

Public API:
  analyze_all_tokens(roi_target_pct, budget_usd)  → full ranked report
  analyze_token(token_id)                          → single token deep analysis
  get_top_picks(n, roi_target_pct)                 → top-N tokens dict list
  get_roi_projection(token_id)                     → projected 12-month return
"""

import json
import logging
import math
import os
import time
from datetime import datetime, timezone
from typing import Optional

import requests
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ─── Config ───────────────────────────────────────────────────────────────────
DEFAULT_ROI_TARGET = 20.0   # percent
DEFAULT_BUDGET     = 1000.0  # USD
MIN_TRUST_SCORE    = 0       # filter out tokens below this trust score
MAX_RISK_SCORE     = 80      # filter out tokens above this risk score
COINGECKO_BASE     = "https://api.coingecko.com/api/v3"

# RWA APY estimates (annual yield baked in even without price gain)
RWA_APY = {
    "ondo-finance":  5.2,
    "centrifuge":    8.5,
    "maple":         9.0,
    "goldfinch":    10.5,
    "clearpool":     8.0,
}

# Priority tokens to always analyze (expanded universe)
PRIORITY_TOKENS = [
    "bitcoin", "ethereum", "chainlink", "aave", "uniswap", "maker",
    "curve-dao-token", "lido-dao", "arbitrum", "optimism",
    "ondo-finance", "centrifuge", "maple", "goldfinch",
    "convex-finance", "pendle", "gains-network", "gmx",
]


# ─── HTTP helper ──────────────────────────────────────────────────────────────

def _get(url: str, params: dict = None, timeout: int = 12) -> Optional[dict]:
    try:
        resp = requests.get(url, params=params, timeout=timeout)
        if resp.status_code == 429:
            time.sleep(60)
            resp = requests.get(url, params=params, timeout=timeout)
        if resp.status_code in (404, 403):
            return None
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        logger.debug("[analyzer] HTTP %s: %s", url, e)
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Technical Indicators
# ═══════════════════════════════════════════════════════════════════════════════

def _ema(prices: list, period: int) -> list:
    """Exponential Moving Average."""
    if len(prices) < period:
        return [sum(prices) / len(prices)] * len(prices)
    k = 2 / (period + 1)
    ema_vals = [sum(prices[:period]) / period]
    for p in prices[period:]:
        ema_vals.append(p * k + ema_vals[-1] * (1 - k))
    return ema_vals


def calc_rsi(prices: list, period: int = 14) -> float:
    """
    RSI (Relative Strength Index) — 0 to 100.
    < 30 = oversold (BUY opportunity)
    > 70 = overbought (SELL signal)
    """
    if len(prices) < period + 1:
        return 50.0  # neutral default
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[i] - prices[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    # Use only last `period` periods
    gains  = gains[-period:]
    losses = losses[-period:]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def calc_macd(prices: list,
              fast: int = 12, slow: int = 26, signal: int = 9) -> dict:
    """
    MACD (Moving Average Convergence Divergence).
    Returns: macd_line, signal_line, histogram, bullish_crossover
    bullish_crossover = True means buy signal (macd crossed above signal)
    """
    if len(prices) < slow + signal:
        return {
            "macd_line": 0.0, "signal_line": 0.0,
            "histogram": 0.0, "bullish_crossover": False,
            "bearish_crossover": False, "trend": "NEUTRAL",
        }
    ema_fast   = _ema(prices, fast)
    ema_slow   = _ema(prices, slow)
    # Align lengths
    offset = len(ema_fast) - len(ema_slow)
    if offset > 0:
        ema_fast = ema_fast[offset:]
    macd_line  = [f - s for f, s in zip(ema_fast, ema_slow)]
    signal_line = _ema(macd_line, signal)
    offset2 = len(macd_line) - len(signal_line)
    if offset2 > 0:
        macd_trimmed = macd_line[offset2:]
    else:
        macd_trimmed = macd_line
    histogram = [m - s for m, s in zip(macd_trimmed, signal_line)]

    latest_macd    = macd_trimmed[-1] if macd_trimmed else 0
    latest_signal  = signal_line[-1] if signal_line else 0
    latest_hist    = histogram[-1] if histogram else 0
    prev_hist      = histogram[-2] if len(histogram) >= 2 else 0

    # Crossover detection
    bullish = (latest_macd > latest_signal and
               (len(macd_trimmed) < 2 or macd_trimmed[-2] <= signal_line[-2]
                if len(signal_line) >= 2 else False))
    bearish = (latest_macd < latest_signal and
               (len(macd_trimmed) < 2 or macd_trimmed[-2] >= signal_line[-2]
                if len(signal_line) >= 2 else False))

    # Trend: histogram growing = strengthening trend
    trend = "NEUTRAL"
    if latest_macd > latest_signal:
        trend = "BULLISH" if latest_hist > prev_hist else "WEAKENING_BULL"
    elif latest_macd < latest_signal:
        trend = "BEARISH" if latest_hist < prev_hist else "WEAKENING_BEAR"

    return {
        "macd_line":          round(latest_macd, 6),
        "signal_line":        round(latest_signal, 6),
        "histogram":          round(latest_hist, 6),
        "bullish_crossover":  bullish,
        "bearish_crossover":  bearish,
        "trend":              trend,
    }


def calc_bollinger(prices: list, period: int = 20, num_std: float = 2.0) -> dict:
    """
    Bollinger Bands — upper / middle / lower bands.
    price near lower band = oversold (BUY)
    price near upper band = overbought (SELL)
    Returns: upper, middle, lower, %B (position within bands), signal
    """
    if len(prices) < period:
        mid = prices[-1] if prices else 0
        return {
            "upper": mid * 1.05, "middle": mid, "lower": mid * 0.95,
            "pct_b": 0.5, "bandwidth": 0.1, "signal": "NEUTRAL",
        }
    window = prices[-period:]
    mid    = sum(window) / period
    std    = math.sqrt(sum((p - mid) ** 2 for p in window) / period)
    upper  = mid + num_std * std
    lower  = mid - num_std * std
    current_price = prices[-1]
    # %B: 0 = at lower band, 1 = at upper band, 0.5 = at middle
    band_range = upper - lower
    pct_b = (current_price - lower) / band_range if band_range > 0 else 0.5
    bandwidth = (band_range / mid) * 100 if mid > 0 else 0  # % width

    if pct_b <= 0.2:
        signal = "OVERSOLD_BUY"
    elif pct_b >= 0.8:
        signal = "OVERBOUGHT_SELL"
    elif pct_b <= 0.35:
        signal = "NEAR_LOWER_BAND"
    elif pct_b >= 0.65:
        signal = "NEAR_UPPER_BAND"
    else:
        signal = "NEUTRAL"

    return {
        "upper":     round(upper, 6),
        "middle":    round(mid, 6),
        "lower":     round(lower, 6),
        "pct_b":     round(pct_b, 3),
        "bandwidth": round(bandwidth, 2),
        "signal":    signal,
    }


def get_technical_signals(prices: list) -> dict:
    """
    Run all 3 technical indicators and return a combined signal score.
    Returns: rsi, macd, bollinger, technical_score (0-60), signal_summary
    """
    rsi  = calc_rsi(prices)
    macd = calc_macd(prices)
    boll = calc_bollinger(prices)

    score = 0
    signals = []

    # RSI scoring (0-20 pts)
    if rsi < 30:
        score += 20
        signals.append(f"RSI={rsi:.0f} OVERSOLD (strong buy)")
    elif rsi < 40:
        score += 14
        signals.append(f"RSI={rsi:.0f} low (mild buy)")
    elif rsi < 55:
        score += 8
        signals.append(f"RSI={rsi:.0f} neutral")
    elif rsi < 70:
        score += 3
        signals.append(f"RSI={rsi:.0f} elevated (hold)")
    else:
        score += 0
        signals.append(f"RSI={rsi:.0f} OVERBOUGHT (avoid)")

    # MACD scoring (0-20 pts)
    if macd["bullish_crossover"]:
        score += 20
        signals.append("MACD bullish crossover (strong buy)")
    elif macd["trend"] == "BULLISH":
        score += 15
        signals.append("MACD bullish trend")
    elif macd["trend"] == "WEAKENING_BULL":
        score += 8
        signals.append("MACD weakening bull (caution)")
    elif macd["trend"] == "NEUTRAL":
        score += 5
        signals.append("MACD neutral")
    elif macd["trend"] == "WEAKENING_BEAR":
        score += 2
        signals.append("MACD weakening bear")
    else:
        score += 0
        signals.append("MACD bearish trend (avoid)")

    # Bollinger scoring (0-20 pts)
    if boll["signal"] == "OVERSOLD_BUY":
        score += 20
        signals.append(f"Bollinger: price at lower band (oversold)")
    elif boll["signal"] == "NEAR_LOWER_BAND":
        score += 14
        signals.append("Bollinger: near lower band (cheap)")
    elif boll["signal"] == "NEUTRAL":
        score += 8
        signals.append(f"Bollinger: neutral (pct_B={boll['pct_b']:.2f})")
    elif boll["signal"] == "NEAR_UPPER_BAND":
        score += 3
        signals.append("Bollinger: near upper band (expensive)")
    else:
        score += 0
        signals.append("Bollinger: overbought (avoid)")

    return {
        "rsi":              rsi,
        "macd":             macd,
        "bollinger":        boll,
        "technical_score":  score,   # 0-60
        "signal_summary":   signals,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 3 — ROI Projection
# ═══════════════════════════════════════════════════════════════════════════════

def calc_roi_projection(token: dict, prices: list) -> dict:
    """
    Project 12-month ROI for a token.

    Components:
      A) Momentum:    extrapolate 30d price change → annual
      B) APY:         RWA tokens get their yield bonus (5-10%)
      C) TVL growth:  growing TVL = institutional confidence
      D) Mean revert: if RSI < 35, likely to bounce (+5-15%)

    Returns projected_roi_pct, roi_score (0-25), breakdown
    """
    token_id = token.get("id", "")
    change_30d  = token.get("change_30d", 0) or 0
    change_7d   = token.get("change_7d",  0) or 0
    change_24h  = token.get("change_24h", 0) or 0
    tvl         = token.get("tvl_usd", 0) or 0
    market_cap  = token.get("market_cap", 0) or 0

    breakdown = {}

    # A: Annualized momentum (30d trend extrapolated, dampened)
    # Dampen aggressively: not every 30d trend continues × 12
    # Use square root dampening: realistic for longer horizons
    monthly_pct = change_30d
    if monthly_pct > 0:
        # Positive momentum: dampen with sqrt (diminishing returns)
        annual_momentum = monthly_pct * math.sqrt(12) * 0.6
    else:
        # Negative momentum: less dampening (bear trends persist)
        annual_momentum = monthly_pct * 4
    breakdown["momentum"] = round(annual_momentum, 2)

    # B: RWA APY bonus
    apy = RWA_APY.get(token_id, 0)
    breakdown["apy"] = apy

    # C: TVL growth signal
    tvl_bonus = 0
    if tvl >= 1_000_000_000:   # $1B+ TVL
        tvl_bonus = 5.0
    elif tvl >= 100_000_000:   # $100M+ TVL
        tvl_bonus = 3.0
    elif tvl >= 10_000_000:    # $10M+ TVL
        tvl_bonus = 1.5
    breakdown["tvl_bonus"] = tvl_bonus

    # D: Mean-reversion upside if technically oversold
    rsi = calc_rsi(prices) if len(prices) >= 15 else 50
    reversion_bonus = 0
    if rsi < 30:
        reversion_bonus = 12.0  # strong oversold bounce expected
    elif rsi < 40:
        reversion_bonus = 6.0
    elif rsi < 50:
        reversion_bonus = 2.0
    breakdown["mean_reversion"] = reversion_bonus

    # Total projected ROI
    projected_roi = (annual_momentum + apy + tvl_bonus + reversion_bonus)
    breakdown["total"] = round(projected_roi, 2)

    # Convert to score (0-25 pts)
    # 20% ROI target → 25 pts; scale linearly
    roi_score = min(25, max(0, (projected_roi / 20.0) * 25))
    roi_score = round(roi_score, 1)

    # ROI confidence (how reliable is this projection?)
    confidence = "HIGH" if (len(prices) >= 25 and tvl > 0) else \
                 "MEDIUM" if len(prices) >= 14 else "LOW"

    return {
        "projected_roi_pct": round(projected_roi, 2),
        "roi_score":         roi_score,
        "roi_breakdown":     breakdown,
        "confidence":        confidence,
        "hits_target":       projected_roi >= DEFAULT_ROI_TARGET,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 4 — Risk Score
# ═══════════════════════════════════════════════════════════════════════════════

def calc_risk_score(token: dict, prices: list, trust_score: int,
                    sentiment_score: float) -> dict:
    """
    Risk score 0 (safe) → 100 (very risky).
    Lower is better.

    Factors:
      Volatility (30d price std dev %)     → 0-30 pts risk
      Market cap size                       → 0-20 pts risk
      Trust score (from verification)       → 0-25 pts risk
      Sentiment (fear/greed)                → 0-15 pts risk
      Price age / listing age               → 0-10 pts risk
    """
    risk = 0
    factors = []

    # A: Volatility (std dev of 30d daily returns)
    if len(prices) >= 10:
        returns = [(prices[i] - prices[i-1]) / prices[i-1]
                   for i in range(1, len(prices))
                   if prices[i-1] > 0]
        if returns:
            mean_r = sum(returns) / len(returns)
            variance = sum((r - mean_r) ** 2 for r in returns) / len(returns)
            std_dev_pct = math.sqrt(variance) * 100
            vol_risk = min(30, std_dev_pct * 3)  # 10% daily std = 30 pts risk
            risk += vol_risk
            factors.append(f"Volatility {std_dev_pct:.1f}%/day ({vol_risk:.0f} pts)")

    # B: Market cap (small cap = more volatile)
    market_cap = token.get("market_cap", 0) or 0
    if market_cap >= 10_000_000_000:      # $10B+
        cap_risk = 0
        factors.append("Large cap >$10B (safe)")
    elif market_cap >= 1_000_000_000:     # $1B-$10B
        cap_risk = 5
        factors.append(f"Mid cap ${market_cap/1e9:.1f}B")
    elif market_cap >= 100_000_000:       # $100M-$1B
        cap_risk = 12
        factors.append(f"Small cap ${market_cap/1e6:.0f}M")
    elif market_cap >= 10_000_000:        # $10M-$100M
        cap_risk = 20
        factors.append(f"Micro cap ${market_cap/1e6:.0f}M (risky)")
    else:
        cap_risk = 20
        factors.append("Very small cap (high risk)")
    risk += cap_risk

    # C: Trust score (lower trust = higher risk)
    trust_risk = max(0, 25 - (trust_score / 4))  # trust=100→0 risk, trust=0→25 risk
    risk += trust_risk
    factors.append(f"Trust {trust_score}/100 ({trust_risk:.0f} pts risk)")

    # D: Sentiment risk
    # sentiment_score = 0.0 (max bearish) → 1.0 (max bullish)
    if sentiment_score < 0.2:       # Extreme fear
        sent_risk = 15
        factors.append("Extreme Fear market (+15 risk)")
    elif sentiment_score < 0.4:     # Fear
        sent_risk = 8
        factors.append("Fear market (+8 risk)")
    elif sentiment_score < 0.6:     # Neutral
        sent_risk = 3
        factors.append("Neutral sentiment (+3 risk)")
    else:                           # Greed
        sent_risk = 0
        factors.append("Positive sentiment (+0 risk)")
    risk += sent_risk

    final_risk = min(100, max(0, round(risk, 1)))

    # Risk label
    if final_risk <= 25:
        label = "LOW"
    elif final_risk <= 50:
        label = "MEDIUM"
    elif final_risk <= 70:
        label = "HIGH"
    else:
        label = "VERY_HIGH"

    return {
        "risk_score": final_risk,
        "risk_label": label,
        "risk_factors": factors,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Final Composite Score + Ranking
# ═══════════════════════════════════════════════════════════════════════════════

def _composite_score(technical_score: float, roi_score: float,
                     trust_score: int, risk_score: float) -> float:
    """
    Composite ranking score out of 100.

    Weights:
      Technical signals   20/100   (RSI/MACD/Bollinger)  
      ROI projection      25/100   (can it hit the target?)
      Trust score         20/100   (is it legitimate?)
      Risk-adjusted       15/100   (lower risk = better)
      Momentum bonus      20/100   (recent 30d performance)

    NOTE: technical_score is already 0-60 internally;
          we normalize it to 0-20 for the composite.
    """
    tech_norm  = (technical_score / 60.0) * 20.0   # 0-20
    roi_norm   = roi_score                           # 0-25
    trust_norm = (trust_score / 100.0) * 20.0       # 0-20
    # Risk: invert (low risk = high score)
    risk_norm  = ((100 - risk_score) / 100.0) * 15.0  # 0-15

    # Remaining 20 pts = bonus from having all data available
    data_bonus = 20.0 if (tech_norm > 0 and roi_norm > 0) else 10.0

    total = tech_norm + roi_norm + trust_norm + risk_norm + data_bonus
    return round(min(100, max(0, total)), 1)


def _price_target(current_price: float, projected_roi_pct: float) -> float:
    """Calculate 12-month price target from projected ROI."""
    if not current_price or current_price <= 0:
        return 0.0
    return round(current_price * (1 + projected_roi_pct / 100), 6)


# ═══════════════════════════════════════════════════════════════════════════════
# STEP 1 — Feed + Full Analysis per Token
# ═══════════════════════════════════════════════════════════════════════════════

def _get_prices_for_token(token_id: str, token_db: dict) -> list:
    """
    Get 30-day price history. First try DB, then live CoinGecko.
    Returns list of floats (daily closes, oldest first).
    """
    # Try DB first
    price_json = token_db.get("price_history_json")
    if price_json:
        try:
            prices = json.loads(price_json)
            if isinstance(prices, list) and len(prices) >= 10:
                return [float(p) for p in prices if p]
        except Exception:
            pass

    # Fetch live from CoinGecko
    data = _get(f"{COINGECKO_BASE}/coins/{token_id}/market_chart", {
        "vs_currency": "usd", "days": "30", "interval": "daily",
    })
    if data and "prices" in data:
        prices = [round(p[1], 6) for p in data["prices"] if len(p) >= 2]
        time.sleep(1.5)
        return prices

    # Fallback: simulate from current price + 30d change
    current = token_db.get("price_usd", 0) or 0
    change_30d = token_db.get("change_30d", 0) or 0
    if current > 0:
        start_price = current / (1 + change_30d / 100)
        step = (current - start_price) / 30
        return [start_price + step * i for i in range(31)]
    return []


def analyze_token(token_id: str, budget_fraction: float = 1.0) -> Optional[dict]:
    """
    Full deep analysis of a single token.

    Args:
        token_id:       CoinGecko ID (e.g. "ondo-finance")
        budget_fraction: what fraction of budget is being considered (0-1)

    Returns:
        Full analysis dict including technicals, ROI, risk, composite score.
    """
    from data_pipeline import get_token, get_rwa_assets, get_latest_sentiment
    from verification_layer import get_verification_report

    token = get_token(token_id)
    if not token:
        return None

    symbol = token.get("symbol", "").upper()
    current_price = token.get("price_usd", 0) or 0

    # Get price history
    prices = _get_prices_for_token(token_id, token)

    # Get trust score
    trust_report = get_verification_report(token_id)
    trust_score = trust_report.get("trust_score", 0) if trust_report else 0

    # Get sentiment
    fg_row = get_latest_sentiment("fear_greed", "MARKET")
    fg_details = fg_row.get("details_json", {}) if fg_row else {}
    fg_value = fg_details.get("value", 50) if isinstance(fg_details, dict) else 50
    sentiment_score = fg_value / 100.0

    news_row = get_latest_sentiment("news_vader", symbol)
    if news_row:
        news_sentiment = news_row.get("score", 0.5)
        # Blend fear_greed + news
        sentiment_score = (sentiment_score + news_sentiment) / 2

    # Also check TVL for RWA tokens
    tvl = 0
    if token.get("is_rwa"):
        rwa_list = get_rwa_assets()
        rwa_row = next((r for r in rwa_list if r.get("id") == token_id), None)
        if rwa_row:
            tvl = rwa_row.get("tvl_usd", 0) or 0
    token["tvl_usd"] = tvl  # merge into token dict

    # Run all 3 analysis steps
    technicals = get_technical_signals(prices) if prices else {
        "rsi": 50, "macd": {"trend": "NEUTRAL"},
        "bollinger": {"signal": "NEUTRAL", "pct_b": 0.5},
        "technical_score": 5, "signal_summary": ["No price history available"],
    }
    roi_analysis = calc_roi_projection(token, prices)
    risk_analysis = calc_risk_score(token, prices, trust_score, sentiment_score)

    # Composite score
    composite = _composite_score(
        technicals["technical_score"],
        roi_analysis["roi_score"],
        trust_score,
        risk_analysis["risk_score"],
    )

    # Price targets
    price_target_12m = _price_target(current_price, roi_analysis["projected_roi_pct"])
    price_target_roi = _price_target(current_price, DEFAULT_ROI_TARGET)

    # Buy/Hold/Avoid recommendation
    if composite >= 65 and risk_analysis["risk_score"] <= 55:
        recommendation = "BUY"
        recommendation_reason = "Strong technicals + good ROI projection + acceptable risk"
    elif composite >= 50 and risk_analysis["risk_score"] <= 65:
        recommendation = "ACCUMULATE"
        recommendation_reason = "Good signals — consider DCA (dollar-cost averaging)"
    elif composite >= 35:
        recommendation = "WATCH"
        recommendation_reason = "Borderline — wait for better entry signal"
    elif risk_analysis["risk_score"] >= 75:
        recommendation = "AVOID"
        recommendation_reason = "Risk too high for 20% ROI target"
    else:
        recommendation = "HOLD"
        recommendation_reason = "Insufficient upside signal currently"

    # Suggested allocation % of budget
    if recommendation == "BUY":
        alloc_pct = min(35, max(5, composite / 3))
    elif recommendation == "ACCUMULATE":
        alloc_pct = min(20, max(3, composite / 5))
    else:
        alloc_pct = 0.0

    return {
        "token_id":      token_id,
        "symbol":        symbol,
        "name":          token.get("name", ""),
        "current_price": current_price,
        "market_cap":    token.get("market_cap", 0),
        "tvl_usd":       tvl,
        "is_rwa":        bool(token.get("is_rwa")),
        "apy_pct":       RWA_APY.get(token_id, 0),

        # Scores
        "composite_score":  composite,
        "trust_score":      trust_score,
        "technical_score":  technicals["technical_score"],
        "roi_score":        roi_analysis["roi_score"],
        "risk_score":       risk_analysis["risk_score"],
        "risk_label":       risk_analysis["risk_label"],

        # Technical details
        "rsi":              technicals["rsi"],
        "macd_trend":       technicals["macd"]["trend"],
        "bollinger_signal": technicals["bollinger"]["signal"],
        "signal_summary":   technicals["signal_summary"],

        # ROI
        "projected_roi_pct":  roi_analysis["projected_roi_pct"],
        "roi_breakdown":      roi_analysis["roi_breakdown"],
        "price_target_12m":   price_target_12m,
        "price_target_roi":   price_target_roi,
        "hits_roi_target":    roi_analysis["hits_target"],
        "confidence":         roi_analysis["confidence"],

        # Risk
        "risk_factors":     risk_analysis["risk_factors"],

        # Recommendation
        "recommendation":        recommendation,
        "recommendation_reason": recommendation_reason,
        "suggested_alloc_pct":   round(alloc_pct, 1),

        # Sentiment
        "sentiment_score":    round(sentiment_score, 3),
        "fear_greed_value":   fg_value,
    }


def get_top_picks(n: int = 10, roi_target_pct: float = DEFAULT_ROI_TARGET,
                  min_trust: int = 0) -> list:
    """
    Analyze all tokens in DB + priority list and return top-N ranked by composite score.

    Args:
        n:              number of top picks to return
        roi_target_pct: target ROI (default 20%)
        min_trust:      minimum trust score to include (default 0 = all)

    Returns:
        List of token analysis dicts, sorted by composite_score descending.
    """
    from data_pipeline import get_all_tokens

    all_tokens = get_all_tokens()
    # Build set of IDs to analyze (DB tokens + priority list)
    ids_to_analyze = set(t["id"] for t in all_tokens)
    ids_to_analyze.update(PRIORITY_TOKENS)

    results = []
    analyzed = 0
    for token_id in ids_to_analyze:
        try:
            analysis = analyze_token(token_id)
            if not analysis:
                continue
            if analysis["trust_score"] < min_trust:
                continue
            results.append(analysis)
            analyzed += 1
            # Rate limit: don't hammer CoinGecko
            if analyzed % 5 == 0:
                time.sleep(2)
        except Exception as e:
            logger.debug("[analyzer] %s: %s", token_id, e)

    # Sort by composite score
    results.sort(key=lambda x: x["composite_score"], reverse=True)
    logger.info("[analyzer] Analyzed %d tokens, top %d selected", analyzed, min(n, len(results)))
    return results[:n]


def analyze_all_tokens(roi_target_pct: float = DEFAULT_ROI_TARGET,
                       budget_usd: float = DEFAULT_BUDGET,
                       top_n: int = 10) -> dict:
    """
    Full portfolio analysis for a given ROI target and budget.
    This is the main function called by the agent.

    Args:
        roi_target_pct: e.g. 20.0 for "20% ROI"
        budget_usd:     e.g. 1000.0 for "$1000 budget"
        top_n:          how many tokens to recommend

    Returns:
        Full report with ranked picks, portfolio allocation, warnings.
    """
    from data_pipeline import get_latest_sentiment, get_data_freshness

    start = time.time()
    logger.info("[analyzer] Starting analysis: ROI target=%.0f%%, budget=$%.0f",
                roi_target_pct, budget_usd)

    # Check data freshness
    freshness = get_data_freshness()
    if not freshness["is_fresh"]:
        logger.warning("[analyzer] Data is %.0f min old — results may be stale",
                       freshness["age_minutes"])

    # Get market context
    fg_row = get_latest_sentiment("fear_greed", "MARKET")
    fg_details = fg_row.get("details_json", {}) if fg_row else {}
    fg_value = fg_details.get("value", 50) if isinstance(fg_details, dict) else 50
    fg_label = fg_row.get("label", "NEUTRAL") if fg_row else "UNKNOWN"

    # Run analysis on priority tokens first (faster, most relevant)
    all_picks = []
    for token_id in PRIORITY_TOKENS:
        try:
            analysis = analyze_token(token_id)
            if analysis:
                all_picks.append(analysis)
            time.sleep(0.5)
        except Exception as e:
            logger.debug("[analyzer] priority %s: %s", token_id, e)

    # Sort and get top N
    all_picks.sort(key=lambda x: x["composite_score"], reverse=True)
    top_picks = all_picks[:top_n]

    # Portfolio allocation
    portfolio = _build_portfolio(top_picks, budget_usd, roi_target_pct)

    # Market condition warning
    warnings = []
    if fg_value < 20:
        warnings.append(
            f"EXTREME FEAR market (Fear&Greed={fg_value}) — "
            "Consider waiting for Fear&Greed > 40 before buying, or use DCA strategy"
        )
    elif fg_value < 40:
        warnings.append(f"FEAR market (Fear&Greed={fg_value}) — Use caution, prefer DCA")
    elif fg_value > 80:
        warnings.append(
            f"EXTREME GREED (Fear&Greed={fg_value}) — Market may be overbought, "
            "wait for pullback before entering"
        )

    # Check if any picks can hit ROI target
    hits_target_count = sum(1 for p in top_picks if p["hits_roi_target"])
    if hits_target_count == 0:
        warnings.append(
            f"WARNING: No token currently projected to hit {roi_target_pct:.0f}% "
            "ROI target under current market conditions. "
            "Consider lowering target to 10-15% or waiting for bull market."
        )

    elapsed = round(time.time() - start, 1)
    logger.info("[analyzer] Analysis complete: %d picks in %.1fs", len(top_picks), elapsed)

    return {
        "roi_target_pct":     roi_target_pct,
        "budget_usd":         budget_usd,
        "top_picks":          top_picks,
        "portfolio":          portfolio,
        "market_context": {
            "fear_greed_value": fg_value,
            "fear_greed_label": fg_label,
            "is_fresh":         freshness["is_fresh"],
            "data_age_min":     freshness["age_minutes"],
        },
        "warnings":           warnings,
        "tokens_analyzed":    len(all_picks),
        "hits_target_count":  hits_target_count,
        "analyzed_at":        datetime.now(timezone.utc).isoformat(),
        "elapsed_s":          elapsed,
    }


def _build_portfolio(picks: list, budget_usd: float,
                     roi_target_pct: float) -> dict:
    """
    Convert top picks into a concrete dollar allocation.
    Only include BUY/ACCUMULATE recommendations.
    Normalize allocations to sum to 100%.
    """
    buyable = [p for p in picks if p["recommendation"] in ("BUY", "ACCUMULATE")]

    if not buyable:
        return {
            "status":      "NO_BUYS",
            "message":     "No tokens meet buy criteria under current conditions",
            "allocations": [],
            "total_invested": 0,
            "projected_return": 0,
        }

    # Normalize allocation %
    total_alloc = sum(p["suggested_alloc_pct"] for p in buyable)
    if total_alloc <= 0:
        total_alloc = 1

    allocations = []
    total_invested = 0
    total_projected_return = 0

    for pick in buyable:
        alloc_pct  = (pick["suggested_alloc_pct"] / total_alloc) * 100
        alloc_usd  = budget_usd * (alloc_pct / 100)
        # Number of tokens you can buy
        qty        = alloc_usd / pick["current_price"] if pick["current_price"] > 0 else 0
        # Projected value at 12m
        proj_val   = alloc_usd * (1 + pick["projected_roi_pct"] / 100)

        total_invested += alloc_usd
        total_projected_return += proj_val

        allocations.append({
            "rank":            picks.index(pick) + 1,
            "symbol":          pick["symbol"],
            "token_id":        pick["token_id"],
            "recommendation":  pick["recommendation"],
            "alloc_pct":       round(alloc_pct, 1),
            "alloc_usd":       round(alloc_usd, 2),
            "buy_price":       pick["current_price"],
            "target_price":    pick["price_target_12m"],
            "quantity":        round(qty, 6),
            "projected_roi":   pick["projected_roi_pct"],
            "projected_value": round(proj_val, 2),
            "risk_label":      pick["risk_label"],
            "trust_score":     pick["trust_score"],
            "reason":          pick["recommendation_reason"],
        })

    portfolio_roi = ((total_projected_return - total_invested) / total_invested * 100
                     if total_invested > 0 else 0)

    return {
        "status":            "OK",
        "allocations":       allocations,
        "total_invested":    round(total_invested, 2),
        "projected_value":   round(total_projected_return, 2),
        "projected_roi_pct": round(portfolio_roi, 2),
        "hits_target":       portfolio_roi >= roi_target_pct,
        "message": (
            f"Portfolio of {len(allocations)} tokens projected to return "
            f"{portfolio_roi:.1f}% in 12 months on ${budget_usd:.0f} budget"
        ),
    }


def get_roi_projection(token_id: str) -> Optional[dict]:
    """Quick ROI projection for a single token (no technicals)."""
    from data_pipeline import get_token
    token = get_token(token_id)
    if not token:
        return None
    prices = _get_prices_for_token(token_id, token)
    return calc_roi_projection(token, prices)


def format_analysis_for_chat(report: dict) -> str:
    """
    Format analyze_all_tokens() result into human-readable chat response.
    Used by the agent to reply to user's "I want 20% ROI" request.
    """
    roi    = report["roi_target_pct"]
    budget = report["budget_usd"]
    ctx    = report["market_context"]
    port   = report["portfolio"]

    lines = [
        f"## Portfolio Analysis — {roi:.0f}% ROI Target on ${budget:.0f} budget",
        f"",
        f"**Market Conditions:** Fear & Greed = {ctx['fear_greed_value']}/100 ({ctx['fear_greed_label']})",
        f"**Tokens Analyzed:** {report['tokens_analyzed']}",
        f"",
    ]

    # Warnings
    if report["warnings"]:
        for w in report["warnings"]:
            lines.append(f"⚠️  {w}")
        lines.append("")

    # Top picks
    lines.append(f"### Top {len(report['top_picks'])} Tokens Ranked")
    lines.append("")
    for i, pick in enumerate(report["top_picks"][:8], 1):
        badge = "🟢" if pick["trust_score"] >= 85 else \
                "🟡" if pick["trust_score"] >= 60 else \
                "🟠" if pick["trust_score"] >= 40 else "🔴"
        reco_emoji = "✅" if pick["recommendation"] == "BUY" else \
                     "📈" if pick["recommendation"] == "ACCUMULATE" else \
                     "👀" if pick["recommendation"] == "WATCH" else "❌"
        lines.append(
            f"**#{i} {pick['symbol']}** {badge} Score={pick['composite_score']:.0f}/100 "
            f"{reco_emoji} {pick['recommendation']}"
        )
        lines.append(
            f"   Price: ${pick['current_price']:.4f} → "
            f"Target: ${pick['price_target_12m']:.4f} "
            f"(+{pick['projected_roi_pct']:.1f}%)"
        )
        lines.append(
            f"   RSI={pick['rsi']:.0f} | MACD={pick['macd_trend']} | "
            f"Risk={pick['risk_label']} | Trust={pick['trust_score']}/100"
        )
        if pick.get("apy_pct"):
            lines.append(f"   APY: {pick['apy_pct']}% (RWA yield included)")
        lines.append("")

    # Portfolio
    if port["status"] == "OK":
        lines.append(f"### Suggested Portfolio Allocation")
        lines.append(f"Projected Return: **{port['projected_roi_pct']:.1f}%** "
                     f"({'✅ Hits target' if port['hits_target'] else '⚠️ Below target'})")
        lines.append("")
        for a in port["allocations"]:
            lines.append(
                f"• **{a['symbol']}** — ${a['alloc_usd']:.0f} ({a['alloc_pct']:.0f}%) "
                f"→ buy {a['quantity']:.4f} at ${a['buy_price']:.4f} "
                f"| target ${a['target_price']:.4f}"
            )
    else:
        lines.append(f"⚠️  {port['message']}")

    return "\n".join(lines)
