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

    # Fetch geopolitical data
    all_articles = []
    all_tones = {}
    for query in GDELT_QUERIES[:3]:  # Limit to avoid rate limits
        articles = fetch_gdelt_articles(query, max_records=15, timespan="14d")
        all_articles.extend(articles)
        tone = fetch_gdelt_tone(query, timespan="30d")
        if tone:
            all_tones[query] = tone

    # Social sentiment
    reddit_crypto = fetch_reddit_sentiment("cryptocurrency", "RWA tokenization", 15)
    reddit_defi = fetch_reddit_sentiment("defi", "real world assets", 10)
    bluesky = fetch_bluesky_posts("RWA tokenization regulation", 15)

    # Policy/trade context
    imf_rates = fetch_imf_indicators("FM", "FPOLM_PA", ["USA", "GBR", "DEU", "JPN", "CHN"])
    trade = fetch_un_comtrade()
    wb_governance = fetch_world_bank_indicator("CC.EST", "US")  # Control of corruption

    data_context = {
        "customer_region": region,
        "macro_regime": macro.get("macro_regime", "UNKNOWN"),
        "gdelt_articles": [
            {"title": a["title"], "source": a["source"], "tone": a["tone"],
             "date": a["date"]}
            for a in all_articles[:25]
        ],
        "gdelt_tone_analysis": all_tones,
        "reddit_sentiment": {
            "crypto_sub": [
                {"title": p["title"], "score": p["score"]}
                for p in reddit_crypto[:10]
            ],
            "defi_sub": [
                {"title": p["title"], "score": p["score"]}
                for p in reddit_defi[:10]
            ],
        },
        "bluesky_posts": [
            {"text": p["text"][:200], "likes": p["like_count"]}
            for p in bluesky[:10]
        ],
        "imf_policy_rates": imf_rates,
        "us_trade_balance": trade,
        "world_bank_governance": wb_governance[:3] if wb_governance else [],
    }

    prompt = (
        "Analyze the geopolitical and regulatory environment for RWA investments "
        f"(customer region: {region}):\n\n"
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

    logger.info(
        "[geopolitical_analysis] Done: score=%s risk=%s",
        analysis.get("overall_score"), analysis.get("overall_risk_level"),
    )

    return {"geopolitical_analysis": analysis}
