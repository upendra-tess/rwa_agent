"""
Financial Analysis Agent
=========================
Analyzes financial conditions, spreads, stablecoin liquidity,
DeFi yields/TVL, RWA market structure, and holder/activity depth.

Sources: Chicago Fed NFCI, FRED, IMF API, World Bank, ECB,
         DefiLlama, CoinGecko, RWA.xyz
"""

import json
import logging

from bedrock_client import BedrockClient
from state import MultiAgentState
from data_sources import (
    fetch_chicago_fed_nfci, fetch_fred_latest, fetch_fred_series,
    fetch_imf_indicators, fetch_ecb_rates,
    fetch_defillama_protocols, fetch_defillama_stablecoins,
    fetch_defillama_yields, fetch_coingecko_market,
)

logger = logging.getLogger(__name__)
bedrock = BedrockClient()

ANALYSIS_SYSTEM_PROMPT = """You are a Financial Analysis Agent for RWA (Real World Asset) investments.

Given financial conditions data, produce a structured analysis covering:

1. FINANCIAL_CONDITIONS: Overall tightness/looseness (NFCI, credit spreads)
2. SPREAD_ANALYSIS: Credit spreads, yield curve shape, term premium
3. STABLECOIN_LIQUIDITY: Stablecoin market health as proxy for DeFi liquidity
4. DEFI_YIELDS: Current DeFi yield landscape and how RWA competes
5. RWA_MARKET_STRUCTURE: TVL distribution, holder concentration, activity depth
6. FUNDING_ENVIRONMENT: How easy it is to deploy capital into RWA

Return ONLY valid JSON:
{
  "financial_conditions": {"nfci_value": <float|null>, "assessment": "<TIGHT|NEUTRAL|LOOSE>", "summary": "<string>"},
  "spread_analysis": {"summary": "<string>", "credit_spread_tight": <bool>, "term_premium_positive": <bool>},
  "stablecoin_liquidity": {"total_mcap": <float>, "assessment": "<STRONG|ADEQUATE|WEAK>", "summary": "<string>"},
  "defi_yields": {"avg_stablecoin_yield": <float>, "rwa_yield_competitive": <bool>, "top_yields": [{"protocol": "<string>", "apy": <float>}], "summary": "<string>"},
  "rwa_market_structure": {"total_tvl": <float>, "concentration_risk": "<LOW|MEDIUM|HIGH>", "summary": "<string>"},
  "funding_environment": {"score": <1-10>, "summary": "<string>"},
  "overall_score": <1-100>,
  "overall_assessment": "<FAVORABLE|NEUTRAL|UNFAVORABLE>"
}"""


def financial_analysis_agent(state: MultiAgentState) -> dict:
    """Run financial conditions analysis."""
    logger.info("[financial_analysis] Starting...")
    macro = state.get("macro_context", {})
    rwa_universe = state.get("rwa_universe", [])

    # Fetch financial data
    nfci = fetch_chicago_fed_nfci()
    fed_funds = fetch_fred_latest("FEDFUNDS")
    baa_spread = fetch_fred_latest("BAAFFM")  # Baa corporate bond spread
    ted_spread = fetch_fred_latest("TEDRATE")  # TED spread
    stablecoins = fetch_defillama_stablecoins()
    defi_yields = fetch_defillama_yields("stablecoin")
    protocols = fetch_defillama_protocols(30)
    ecb = fetch_ecb_rates()

    # Aggregate RWA universe stats
    total_rwa_tvl = sum(a["tvl"] for a in rwa_universe)
    by_type = {}
    for a in rwa_universe:
        t = a.get("asset_type", "other")
        by_type.setdefault(t, {"count": 0, "tvl": 0})
        by_type[t]["count"] += 1
        by_type[t]["tvl"] += a["tvl"]

    data_context = {
        "macro_regime": macro.get("macro_regime", "UNKNOWN"),
        "rate_environment": macro.get("rate_environment", "UNKNOWN"),
        "key_rates": macro.get("key_rates", {}),
        "nfci": nfci,
        "fed_funds_rate": fed_funds,
        "baa_corporate_spread": baa_spread,
        "ted_spread": ted_spread,
        "ecb_rates": ecb,
        "stablecoin_market": {
            "total_mcap": stablecoins.get("total_stablecoin_mcap", 0),
            "top_stablecoins": stablecoins.get("top_stablecoins", [])[:5],
        },
        "defi_yields": [
            {"protocol": y["project"], "symbol": y["symbol"],
             "apy": y["apy"], "tvl": y["tvl"]}
            for y in defi_yields[:15]
        ],
        "top_protocols_by_tvl": [
            {"name": p["name"], "tvl": p["tvl"], "category": p["category"]}
            for p in protocols[:15]
        ],
        "rwa_market": {
            "total_tvl": total_rwa_tvl,
            "asset_count": len(rwa_universe),
            "by_asset_type": by_type,
            "top_protocols": [
                {"name": a["name"], "tvl": a["tvl"], "asset_type": a["asset_type"]}
                for a in rwa_universe[:15]
            ],
        },
    }

    prompt = (
        "Analyze the financial conditions for RWA investment based on this data:\n\n"
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
        logger.warning("[financial_analysis] Failed to parse LLM response")
        analysis = {
            "overall_score": 50,
            "overall_assessment": "NEUTRAL",
            "financial_conditions": {"nfci_value": nfci, "assessment": "NEUTRAL", "summary": "Parse error"},
            "spread_analysis": {"summary": "Unavailable"},
            "stablecoin_liquidity": {"total_mcap": 0, "assessment": "ADEQUATE", "summary": "Unavailable"},
            "defi_yields": {"summary": "Unavailable"},
            "rwa_market_structure": {"total_tvl": 0, "summary": "Unavailable"},
            "funding_environment": {"score": 5, "summary": "Unavailable"},
        }

    analysis["_raw_data"] = {
        "nfci": nfci,
        "stablecoins": stablecoins,
        "defi_yields": defi_yields[:10],
    }

    logger.info(
        "[financial_analysis] Done: score=%s assessment=%s",
        analysis.get("overall_score"), analysis.get("overall_assessment"),
    )

    return {"financial_analysis": analysis}
