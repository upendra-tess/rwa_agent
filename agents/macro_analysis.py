"""
Macro Analysis Agent
=====================
Fetches macro-economic context and classifies the current environment.
Feeds into the 5 parallel analysis agents.

Sources: Treasury.gov, FRED, World Bank, IMF, ECB, Yahoo Finance
"""

import logging
from typing import Optional

from bedrock_client import BedrockClient
from state import MultiAgentState
from data_sources import (
    fetch_treasury_yields, fetch_fred_latest, fetch_gdpnow,
    fetch_chicago_fed_nfci, fetch_world_bank_indicator,
    fetch_imf_indicators, fetch_ecb_rates,
)

logger = logging.getLogger(__name__)
bedrock = BedrockClient()


def _classify_rate_environment(yields: dict, fed_funds: Optional[float]) -> str:
    y10 = yields.get("yield_10y", 0)
    y3m = yields.get("yield_3m", 0)
    if not y10:
        return "UNKNOWN"
    if y3m and y3m > y10 + 0.5:
        return "RISING"
    if y10 >= 4.5:
        return "HIGH_RATES"
    if y10 >= 3.5:
        if fed_funds and y10 < fed_funds - 0.25:
            return "NORMALIZING"
        return "HIGH_RATES"
    if y10 >= 2.5:
        return "NORMALIZING"
    return "LOW_RATES"


def _classify_macro_regime(yields: dict, vix: Optional[float]) -> str:
    y10 = yields.get("yield_10y", 0)
    y2 = yields.get("yield_2y", 0)
    inverted = bool(y2 and y10 and y2 > y10)
    high_vix = bool(vix and vix > 25)
    high_rates = bool(y10 and y10 > 4.5)

    if inverted and high_vix:
        return "RISK_OFF"
    if high_rates and high_vix:
        return "STAGFLATION"
    if inverted:
        return "RISK_OFF"
    if high_rates:
        return "RISK_ON"
    return "GOLDILOCKS"


def _compute_rwa_attractiveness(yields: dict, macro_regime: str,
                                 rate_env: str, vix: Optional[float]) -> tuple:
    score = 50
    y10 = yields.get("yield_10y", 0)
    y3m = yields.get("yield_3m", 0)

    rate_adj = {"NORMALIZING": 20, "LOW_RATES": 15, "HIGH_RATES": -5, "RISING": -20}
    score += rate_adj.get(rate_env, 0)

    regime_adj = {"GOLDILOCKS": 15, "RISK_ON": 5, "RISK_OFF": -15, "STAGFLATION": -20}
    score += regime_adj.get(macro_regime, 0)

    if vix:
        score += 10 if vix < 15 else (-15 if vix > 30 else 0)

    if y10 and y3m:
        spread = y10 - y3m
        score += 5 if spread > 0.5 else (-10 if spread < -0.5 else 0)

    score = max(0, min(100, score))
    if score >= 75:
        label = "VERY_ATTRACTIVE"
    elif score >= 55:
        label = "ATTRACTIVE"
    elif score >= 40:
        label = "NEUTRAL"
    elif score >= 20:
        label = "CAUTIOUS"
    else:
        label = "AVOID"
    return score, label


def macro_analysis_agent(state: MultiAgentState) -> dict:
    """Fetch macro data and classify the environment."""
    logger.info("[macro_analysis] Fetching macro context...")

    # Fetch all macro data
    yields = fetch_treasury_yields()
    fed_funds = fetch_fred_latest("FEDFUNDS")
    gdpnow = fetch_gdpnow()
    nfci = fetch_chicago_fed_nfci()
    cpi = fetch_fred_latest("CPIAUCSL")
    wb_gdp = fetch_world_bank_indicator("NY.GDP.MKTP.KD.ZG", "US")
    imf_rates = fetch_imf_indicators("FM", "FPOLM_PA", ["USA", "GBR", "DEU", "JPN"])
    ecb = fetch_ecb_rates()

    # Fetch VIX via Yahoo (using existing helper or direct)
    vix = None
    try:
        import requests
        resp = requests.get(
            "https://query1.finance.yahoo.com/v8/finance/chart/%5EVIX",
            params={"interval": "1d", "range": "5d"},
            headers={"User-Agent": "Mozilla/5.0"}, timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            closes = data["chart"]["result"][0]["indicators"]["quote"][0]["close"]
            closes = [c for c in closes if c is not None]
            vix = round(float(closes[-1]), 2) if closes else None
    except Exception:
        pass

    # Classify environment
    rate_env = _classify_rate_environment(yields, fed_funds)
    macro_regime = _classify_macro_regime(yields, vix)
    rwa_score, rwa_label = _compute_rwa_attractiveness(
        yields, macro_regime, rate_env, vix)

    macro_context = {
        "rate_environment": rate_env,
        "macro_regime": macro_regime,
        "rwa_attractiveness_score": rwa_score,
        "rwa_attractiveness_label": rwa_label,
        "key_rates": {
            "fed_funds": fed_funds,
            "yield_3m": yields.get("yield_3m"),
            "yield_2y": yields.get("yield_2y"),
            "yield_10y": yields.get("yield_10y"),
            "yield_30y": yields.get("yield_30y"),
            "yield_curve_spread": (
                round(yields.get("yield_10y", 0) - yields.get("yield_2y", 0), 3)
                if yields.get("yield_10y") and yields.get("yield_2y") else None
            ),
        },
        "market_indicators": {
            "vix": vix,
            "nfci": nfci,
            "gdpnow": gdpnow,
            "cpi_index": cpi,
        },
        "global_context": {
            "ecb_rates": ecb,
            "imf_policy_rates": imf_rates,
            "world_bank_gdp": wb_gdp[:3] if wb_gdp else [],
        },
    }

    logger.info(
        "[macro_analysis] regime=%s rate_env=%s rwa=%d/100 (%s)",
        macro_regime, rate_env, rwa_score, rwa_label,
    )

    return {"macro_context": macro_context}
