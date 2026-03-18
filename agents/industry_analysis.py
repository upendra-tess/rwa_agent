"""
Industry Analysis Agent
========================
Analyzes underlying sector growth, rates backdrop, chain activity,
tokenized asset-class growth, and liquidity by chain/platform.

Sources: FRED, IMF API, World Bank, ECB Data Portal, GDPNow/FRED,
         DefiLlama, CoinGecko, GeckoTerminal, RWA.xyz
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from agents.utils import extract_json

from bedrock_client import BedrockClient
from state import MultiAgentState
from data_sources import (
    fetch_fred_latest, fetch_gdpnow,
    fetch_world_bank_indicator, fetch_imf_indicators, fetch_ecb_rates,
    fetch_defillama_protocols, fetch_defillama_chains,
    fetch_coingecko_market, fetch_gecko_terminal_pools,
)

logger = logging.getLogger(__name__)
bedrock = BedrockClient()

ANALYSIS_SYSTEM_PROMPT = """You are an Industry Analysis Agent specializing in Real World Asset (RWA) tokenization.

Given the macro context and raw data, produce a structured industry analysis covering:

1. SECTOR_GROWTH: Underlying sector growth trends for tokenized assets (treasuries, credit, real estate, commodities)
2. RATES_BACKDROP: How current interest rates affect RWA attractiveness vs TradFi
3. CHAIN_ACTIVITY: Which blockchains have the most RWA activity and TVL growth
4. ASSET_CLASS_GROWTH: Growth rates of different tokenized asset classes
5. LIQUIDITY_ASSESSMENT: Liquidity depth by chain and platform
6. INDUSTRY_RISKS: Key risks to the RWA tokenization industry

IMPORTANT: Keep ALL text fields under 25 words. Be concise.

Return ONLY valid JSON:
{
  "sector_growth": {"summary": "<string>", "score": <1-10>, "details": [<strings>]},
  "rates_backdrop": {"summary": "<string>", "score": <1-10>, "favorable": <bool>},
  "chain_activity": {"top_chains": [{"name": "<string>", "tvl": <float>, "trend": "<string>"}], "summary": "<string>"},
  "asset_class_growth": {"categories": [{"name": "<string>", "growth_trend": "<string>", "tvl": <float>}], "summary": "<string>"},
  "liquidity_assessment": {"score": <1-10>, "summary": "<string>", "concerns": [<strings>]},
  "industry_risks": [<strings>],
  "overall_score": <1-100>,
  "overall_outlook": "<BULLISH|NEUTRAL|BEARISH>"
}"""


def industry_analysis_agent(state: MultiAgentState) -> dict:
    """Run industry analysis using macro context + live RWA universe."""
    logger.info("[industry_analysis] Starting...")
    macro = state.get("macro_context", {})
    rwa_universe = state.get("rwa_universe", [])

    # Fetch supplementary data in parallel
    gecko_ids = [a["gecko_id"] for a in rwa_universe if a.get("gecko_id")][:20]
    futures = {}
    with ThreadPoolExecutor(max_workers=7) as pool:
        futures["protocols"] = pool.submit(fetch_defillama_protocols, 50)
        futures["chains"] = pool.submit(fetch_defillama_chains)
        futures["dex_pools"] = pool.submit(fetch_gecko_terminal_pools, "eth", 15)
        futures["gdpnow"] = pool.submit(fetch_gdpnow)
        futures["wb_gdp"] = pool.submit(fetch_world_bank_indicator, "NY.GDP.MKTP.KD.ZG", "US")
        futures["ecb"] = pool.submit(fetch_ecb_rates)
        if gecko_ids:
            futures["rwa_tokens"] = pool.submit(fetch_coingecko_market, gecko_ids)

    protocols = futures["protocols"].result()
    chains = futures["chains"].result()
    dex_pools = futures["dex_pools"].result()
    gdpnow = futures["gdpnow"].result()
    wb_gdp = futures["wb_gdp"].result()
    ecb = futures["ecb"].result()
    rwa_tokens = futures["rwa_tokens"].result() if "rwa_tokens" in futures else []

    # Aggregate RWA universe by asset type and chain
    by_asset_type = {}
    by_chain = {}
    for a in rwa_universe:
        t = a.get("asset_type", "other")
        by_asset_type.setdefault(t, {"count": 0, "tvl": 0})
        by_asset_type[t]["count"] += 1
        by_asset_type[t]["tvl"] += a.get("tvl", 0)
        for c in (a.get("chains") or [a.get("chain", "Unknown")]):
            by_chain.setdefault(c, {"count": 0, "tvl": 0})
            by_chain[c]["count"] += 1
            by_chain[c]["tvl"] += a.get("tvl", 0)

    data_context = {
        "macro_regime": macro.get("macro_regime", "UNKNOWN"),
        "rate_environment": macro.get("rate_environment", "UNKNOWN"),
        "rwa_attractiveness": macro.get("rwa_attractiveness_label", "UNKNOWN"),
        "key_rates": macro.get("key_rates", {}),
        "gdpnow_estimate": gdpnow,
        "world_bank_gdp": wb_gdp[:3] if wb_gdp else [],
        "ecb_rates": ecb,
        "rwa_universe_summary": {
            "total_protocols": len(rwa_universe),
            "total_tvl": sum(a["tvl"] for a in rwa_universe),
            "by_asset_type": by_asset_type,
            "by_chain": dict(sorted(by_chain.items(), key=lambda x: x[1]["tvl"], reverse=True)[:5]),
        },
        "top_rwa_protocols": [
            {"name": a["name"], "tvl": a["tvl"], "asset_type": a["asset_type"],
             "change_7d": a.get("change_7d")}
            for a in rwa_universe[:10]
        ],
        "rwa_token_prices": [
            {"symbol": t["symbol"], "market_cap": t["market_cap"], "change_30d": t.get("change_30d")}
            for t in rwa_tokens[:8]
        ],
        "top_defi_protocols": [
            {"name": p["name"], "tvl": p["tvl"], "category": p["category"]}
            for p in protocols[:5]
        ],
        "chain_tvl": [
            {"name": c["name"], "tvl": c["tvl"]}
            for c in chains[:5]
        ],
        "dex_activity": [
            {"name": p["name"], "volume_24h": p["volume_24h"]}
            for p in dex_pools[:5]
        ],
    }

    prompt = (
        "Analyze the RWA tokenization industry based on this data:\n\n"
        f"{json.dumps(data_context, default=str)}"
    )

    logger.info("[industry_analysis] Sending to LLM for analysis...")
    try:
        raw = bedrock.send_message(prompt, system_prompt=ANALYSIS_SYSTEM_PROMPT)
        logger.info("[industry_analysis] LLM response received, parsing...")
        analysis = extract_json(raw)
    except Exception as e:
        logger.warning("[industry_analysis] Failed to parse LLM response")
        analysis = {
            "overall_score": 50,
            "overall_outlook": "NEUTRAL",
            "sector_growth": {"summary": "Analysis unavailable", "score": 5},
            "rates_backdrop": {"summary": "Analysis unavailable", "score": 5, "favorable": True},
            "chain_activity": {"top_chains": [], "summary": "Data unavailable"},
            "asset_class_growth": {"categories": [], "summary": "Data unavailable"},
            "liquidity_assessment": {"score": 5, "summary": "Data unavailable", "concerns": []},
            "industry_risks": [],
        }

    # Attach raw data for downstream agents
    analysis["_raw_data"] = {
        "rwa_tokens": rwa_tokens,
        "protocols": protocols[:20],
        "chains": chains[:10],
    }

    logger.info(
        "[industry_analysis] Done: score=%s outlook=%s",
        analysis.get("overall_score"), analysis.get("overall_outlook"),
    )

    return {"industry_analysis": analysis}
