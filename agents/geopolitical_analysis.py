"""
Geopolitical Analysis Agent
============================
Analyzes geopolitical risks, regulatory trends, sanctions exposure,
and policy environment affecting RWA investments.

Sources: GDELT, GDELT tone/topic scoring + internal NLP,
         Reddit API, Bluesky public API,
         RWA.xyz, DefiLlama, IMF/World Bank/Comtrade/OFAC
"""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from agents.utils import extract_json

from bedrock_client import BedrockClient
from state import MultiAgentState
from data_sources import (
    fetch_gdelt_articles, fetch_gdelt_tone,
    fetch_reddit_sentiment, fetch_bluesky_posts,
    fetch_defillama_protocols,
    fetch_world_bank_indicator, fetch_imf_indicators,
    fetch_un_comtrade,
)

logger = logging.getLogger(__name__)
bedrock = BedrockClient()

# Key geopolitical queries for GDELT
GDELT_QUERIES = [
    "tokenization regulation cryptocurrency",
    "RWA real world assets blockchain",
    "SEC crypto regulation enforcement",
    "OFAC sanctions cryptocurrency",
    "central bank digital currency CBDC",
    "stablecoin regulation",
]

ANALYSIS_SYSTEM_PROMPT = """You are a Geopolitical Analysis Agent for RWA (Real World Asset) investments.

Given news articles, social sentiment, and policy data, produce a structured geopolitical analysis:

1. REGULATORY_LANDSCAPE: Current regulatory environment for tokenized assets (US SEC, EU MiCA, APAC)
2. SANCTIONS_RISK: OFAC/sanctions exposure for RWA protocols and their underlying assets
3. POLICY_TRENDS: Direction of crypto/RWA regulation (tightening, loosening, stable)
4. GEOPOLITICAL_EVENTS: Key events that could impact RWA markets
5. SOCIAL_SENTIMENT: Public/community sentiment on RWA regulation and adoption
6. REGIONAL_RISK_MAP: Risk assessment by major region (US, EU, APAC, EM)

IMPORTANT: Keep ALL text fields under 25 words. Be concise.

Return ONLY valid JSON:
{
  "regulatory_landscape": {"summary": "<string>", "us_outlook": "<FAVORABLE|NEUTRAL|HOSTILE>", "eu_outlook": "<FAVORABLE|NEUTRAL|HOSTILE>", "apac_outlook": "<FAVORABLE|NEUTRAL|HOSTILE>"},
  "sanctions_risk": {"level": "<LOW|MEDIUM|HIGH>", "summary": "<string>", "flagged_concerns": [<strings>]},
  "policy_trends": {"direction": "<TIGHTENING|STABLE|LOOSENING>", "summary": "<string>", "key_developments": [<strings>]},
  "geopolitical_events": [{"event": "<string>", "impact": "<POSITIVE|NEUTRAL|NEGATIVE>", "severity": <1-10>}],
  "social_sentiment": {"overall": "<POSITIVE|NEUTRAL|NEGATIVE>", "key_themes": [<strings>], "summary": "<string>"},
  "regional_risk_map": [{"region": "<string>", "risk_level": "<LOW|MEDIUM|HIGH>", "notes": "<string>"}],
  "overall_score": <1-100>,
  "overall_risk_level": "<LOW|MEDIUM|HIGH|CRITICAL>"
}"""


def geopolitical_analysis_agent(state: MultiAgentState) -> dict:
    """Run geopolitical analysis using news, social, and policy data."""
    logger.info("[geopolitical_analysis] Starting...")
    macro = state.get("macro_context", {})
    customer = state.get("customer_profile", {})
    region = customer.get("region", "US")

    # Fetch all geopolitical data in parallel
    queries = GDELT_QUERIES[:3]
    with ThreadPoolExecutor(max_workers=12) as pool:
        # GDELT articles + tones (3 queries x 2 calls = 6)
        f_articles = {q: pool.submit(fetch_gdelt_articles, q, 15, "14d") for q in queries}
        f_tones = {q: pool.submit(fetch_gdelt_tone, q, "30d") for q in queries}
        # Social sentiment
        f_reddit_crypto = pool.submit(fetch_reddit_sentiment, "cryptocurrency", "RWA tokenization", 15)
        f_reddit_defi = pool.submit(fetch_reddit_sentiment, "defi", "real world assets", 10)
        f_bluesky = pool.submit(fetch_bluesky_posts, "RWA tokenization regulation", 15)
        # Policy/trade context
        f_imf = pool.submit(fetch_imf_indicators, "FM", "FPOLM_PA", ["USA", "GBR", "DEU", "JPN", "CHN"])
        f_trade = pool.submit(fetch_un_comtrade)
        f_wb = pool.submit(fetch_world_bank_indicator, "CC.EST", "US")

    all_articles = []
    all_tones = {}
    for q in queries:
        all_articles.extend(f_articles[q].result())
        tone = f_tones[q].result()
        if tone:
            all_tones[q] = tone

    reddit_crypto = f_reddit_crypto.result()
    reddit_defi = f_reddit_defi.result()
    bluesky = f_bluesky.result()
    imf_rates = f_imf.result()
    trade = f_trade.result()
    wb_governance = f_wb.result()

    data_context = {
        "customer_region": region,
        "macro_regime": macro.get("macro_regime", "UNKNOWN"),
        "gdelt_articles": [
            {"title": a["title"], "tone": a["tone"]}
            for a in all_articles[:12]
        ],
        "gdelt_tone_analysis": all_tones,
        "reddit_sentiment": {
            "crypto_sub": [
                {"title": p["title"], "score": p["score"]}
                for p in reddit_crypto[:5]
            ],
            "defi_sub": [
                {"title": p["title"], "score": p["score"]}
                for p in reddit_defi[:5]
            ],
        },
        "bluesky_posts": [
            {"text": p["text"][:100], "likes": p["like_count"]}
            for p in bluesky[:5]
        ],
        "imf_policy_rates": imf_rates,
        "us_trade_balance": trade,
        "world_bank_governance": wb_governance[:3] if wb_governance else [],
    }

    prompt = (
        "Analyze the geopolitical and regulatory environment for RWA investments "
        f"(customer region: {region}):\n\n"
        f"{json.dumps(data_context, default=str)}"
    )

    logger.info("[geopolitical_analysis] Sending to LLM for analysis...")
    try:
        raw = bedrock.send_message(prompt, system_prompt=ANALYSIS_SYSTEM_PROMPT)
        logger.info("[geopolitical_analysis] LLM response received, parsing...")
        analysis = extract_json(raw)
    except Exception as e:
        logger.warning("[geopolitical_analysis] Failed to parse LLM response")
        analysis = {
            "overall_score": 50,
            "overall_risk_level": "MEDIUM",
            "regulatory_landscape": {"summary": "Parse error", "us_outlook": "NEUTRAL"},
            "sanctions_risk": {"level": "LOW", "summary": "Unavailable"},
            "policy_trends": {"direction": "STABLE", "summary": "Unavailable"},
            "geopolitical_events": [],
            "social_sentiment": {"overall": "NEUTRAL", "summary": "Unavailable"},
            "regional_risk_map": [],
        }

    # Attach raw signals for qualitative context in output
    analysis["_key_signals"] = {
        "gdelt_top_articles": [
            {"title": a["title"], "tone": a["tone"], "source": a["source"]}
            for a in all_articles[:5] if a.get("title")
        ],
        "gdelt_tones": all_tones,
        "reddit_top": [
            p["title"] for p in (reddit_crypto + reddit_defi)[:3] if p.get("title")
        ],
        "imf_policy_rates": imf_rates,
    }

    logger.info(
        "[geopolitical_analysis] Done: score=%s risk=%s",
        analysis.get("overall_score"), analysis.get("overall_risk_level"),
    )

    return {"geopolitical_analysis": analysis}
