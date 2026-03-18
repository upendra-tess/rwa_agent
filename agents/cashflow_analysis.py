"""
Cash Flow Agent
================
Analyzes discount-rate inputs, trade-linked cash-flow exposure,
on-chain yield competition, tokenized product growth, and transfer activity.

Sources: FRED, IMF API, World Bank, UN Comtrade,
         DefiLlama, CoinGecko/GeckoTerminal, RWA.xyz + issuer disclosures
"""

import json
import logging

from bedrock_client import BedrockClient
from state import MultiAgentState
from data_sources import (
    fetch_fred_latest, fetch_fred_series, fetch_treasury_yields,
    fetch_world_bank_indicator, fetch_un_comtrade,
    fetch_defillama_yields, fetch_defillama_protocols,
    fetch_coingecko_market, fetch_gecko_terminal_pools,
)

logger = logging.getLogger(__name__)
bedrock = BedrockClient()

ANALYSIS_SYSTEM_PROMPT = """You are a Cash Flow Analysis Agent for RWA (Real World Asset) investments.

Given discount-rate data, trade flows, yield competition, and issuer disclosures, produce a structured analysis:

1. DISCOUNT_RATE_ANALYSIS: Current risk-free rates and implied discount rates for RWA cash flows
2. TRADE_LINKED_EXPOSURE: How global trade flows affect underlying RWA collateral
3. YIELD_COMPETITION: On-chain yield landscape vs RWA yields (are RWA yields competitive?)
4. PRODUCT_GROWTH: Growth of tokenized products (TVL, new issuances, transfer volume)
5. ISSUER_ASSESSMENT: Quality assessment of RWA issuers based on disclosures
6. CASH_FLOW_RISKS: Key risks to RWA cash flow sustainability

Return ONLY valid JSON:
{
  "discount_rate_analysis": {"risk_free_rate": <float>, "implied_spread": <float>, "summary": "<string>"},
  "trade_linked_exposure": {"trade_balance_usd": <float|null>, "exposure_level": "<LOW|MEDIUM|HIGH>", "summary": "<string>"},
  "yield_competition": {"avg_defi_yield": <float>, "avg_rwa_yield": <float>, "rwa_competitive": <bool>, "summary": "<string>"},
  "product_growth": {"total_rwa_tvl": <float>, "growth_trend": "<GROWING|STABLE|DECLINING>", "summary": "<string>"},
  "issuer_assessment": [{"issuer": "<string>", "quality_score": <1-10>, "key_risk": "<string>"}],
  "cashflow_risks": [<strings>],
  "overall_score": <1-100>,
  "overall_assessment": "<STRONG_CASHFLOWS|ADEQUATE|WEAK_CASHFLOWS>"
}"""


def cashflow_analysis_agent(state: MultiAgentState) -> dict:
    """Run cash flow analysis."""
    logger.info("[cashflow_analysis] Starting...")
    macro = state.get("macro_context", {})
    rwa_universe = state.get("rwa_universe", [])

    # Fetch cash flow relevant data
    yields = fetch_treasury_yields()
    fed_funds = fetch_fred_latest("FEDFUNDS")
    real_rate = fetch_fred_latest("DFII10")  # 10Y TIPS real yield
    trade = fetch_un_comtrade()

    defi_yields = fetch_defillama_yields()
    protocols = fetch_defillama_protocols(30)

    # Get CoinGecko prices for top RWA tokens with gecko_ids
    gecko_ids = [a["gecko_id"] for a in rwa_universe if a.get("gecko_id")][:15]
    rwa_tokens = fetch_coingecko_market(gecko_ids) if gecko_ids else []

    # Avg DeFi stablecoin yield
    stable_yields = [y["apy"] for y in defi_yields if y["apy"] and 0 < y["apy"] < 50]
    avg_defi_yield = sum(stable_yields) / len(stable_yields) if stable_yields else 5.0

    # Estimate avg RWA yield from universe asset types
    rwa_apy_estimates = {
        "treasury": 4.5, "gold": 0, "stablecoin_rwa": 5.0,
        "credit": 8.0, "real_estate": 7.0, "insurance": 6.0,
        "equity": 3.0, "yield": 10.0, "commodity": 2.0, "other": 5.0,
    }
    rwa_apys = [rwa_apy_estimates.get(a.get("asset_type", "other"), 5.0) for a in rwa_universe[:20]]
    avg_rwa_yield = sum(rwa_apys) / len(rwa_apys) if rwa_apys else 5.0

    total_rwa_tvl = sum(a["tvl"] for a in rwa_universe)

    data_context = {
        "macro_regime": macro.get("macro_regime", "UNKNOWN"),
        "rate_environment": macro.get("rate_environment", "UNKNOWN"),
        "key_rates": macro.get("key_rates", {}),
        "risk_free_3m": yields.get("yield_3m"),
        "risk_free_10y": yields.get("yield_10y"),
        "real_rate_10y": real_rate,
        "fed_funds": fed_funds,
        "trade_data": trade,
        "avg_defi_yield": round(avg_defi_yield, 2),
        "avg_rwa_yield": round(avg_rwa_yield, 2),
        "rwa_market_tvl": total_rwa_tvl,
        "rwa_universe_top": [
            {"name": a["name"], "tvl": a["tvl"], "asset_type": a["asset_type"],
             "chain": a["chain"]}
            for a in rwa_universe[:15]
        ],
        "rwa_token_prices": [
            {"symbol": t["symbol"], "market_cap": t["market_cap"],
             "change_30d": t.get("change_30d")}
            for t in rwa_tokens
        ],
        "top_defi_yields": [
            {"protocol": y["project"], "apy": y["apy"], "tvl": y["tvl"]}
            for y in defi_yields[:10]
        ],
    }

    prompt = (
        "Analyze the cash flow dynamics for RWA investments based on this data:\n\n"
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
        logger.warning("[cashflow_analysis] Failed to parse LLM response")
        analysis = {
            "overall_score": 50,
            "overall_assessment": "ADEQUATE",
            "discount_rate_analysis": {"risk_free_rate": yields.get("yield_3m", 0), "summary": "Parse error"},
            "yield_competition": {"avg_defi_yield": avg_defi_yield, "avg_rwa_yield": avg_rwa_yield, "summary": "Unavailable"},
            "product_growth": {"total_rwa_tvl": total_rwa_tvl, "summary": "Unavailable"},
            "issuer_assessment": [],
            "cashflow_risks": [],
        }

    logger.info(
        "[cashflow_analysis] Done: score=%s assessment=%s",
        analysis.get("overall_score"), analysis.get("overall_assessment"),
    )

    return {"cashflow_analysis": analysis}
