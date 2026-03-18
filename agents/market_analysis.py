"""
Market Analysis Agent
======================
Analyzes market sentiment, news flow, social signals, and on-chain
market data for RWA and broader crypto markets.

Sources: GDELT, Alpha Vantage News & Sentiment, NewsAPI,
         Alpha Vantage sentiment + internal NLP,
         Reddit API, Bluesky public API,
         DefiLlama, CoinGecko, GeckoTerminal, RWA.xyz
"""

import json
import logging

from bedrock_client import BedrockClient
from state import MultiAgentState
from data_sources import (
    fetch_gdelt_articles, fetch_gdelt_tone,
    fetch_alpha_vantage_news, fetch_newsapi_articles,
    fetch_reddit_sentiment, fetch_bluesky_posts,
    fetch_defillama_protocols, fetch_defillama_stablecoins,
    fetch_coingecko_market, fetch_gecko_terminal_pools,
)

logger = logging.getLogger(__name__)
bedrock = BedrockClient()

ANALYSIS_SYSTEM_PROMPT = """You are a Market Analysis Agent for RWA (Real World Asset) investments.

Given news, sentiment, social signals, and on-chain data, produce a market analysis:

1. NEWS_SENTIMENT: Overall news tone toward RWA/crypto markets
2. SOCIAL_SENTIMENT: Community sentiment from Reddit, Bluesky, social media
3. MARKET_MOMENTUM: Price trends, volume analysis, fear/greed proxy
4. ON_CHAIN_SIGNALS: TVL trends, DEX activity, stablecoin flows
5. RWA_SPECIFIC_SIGNALS: RWA-specific market signals (new protocols, TVL growth, yield trends)
6. MARKET_RISKS: Key market risks and potential catalysts

Return ONLY valid JSON:
{
  "news_sentiment": {"score": <-1.0 to 1.0>, "label": "<VERY_BEARISH|BEARISH|NEUTRAL|BULLISH|VERY_BULLISH>", "key_headlines": [<strings>], "summary": "<string>"},
  "social_sentiment": {"score": <-1.0 to 1.0>, "label": "<BEARISH|NEUTRAL|BULLISH>", "trending_topics": [<strings>], "summary": "<string>"},
  "market_momentum": {"trend": "<STRONG_UP|UP|SIDEWAYS|DOWN|STRONG_DOWN>", "volume_trend": "<INCREASING|STABLE|DECREASING>", "summary": "<string>"},
  "onchain_signals": {"tvl_trend": "<GROWING|STABLE|DECLINING>", "stablecoin_flows": "<INFLOW|NEUTRAL|OUTFLOW>", "dex_activity": "<HIGH|MEDIUM|LOW>", "summary": "<string>"},
  "rwa_specific_signals": {"adoption_trend": "<ACCELERATING|STEADY|SLOWING>", "yield_trend": "<RISING|STABLE|FALLING>", "new_developments": [<strings>], "summary": "<string>"},
  "market_risks": [{"risk": "<string>", "probability": "<LOW|MEDIUM|HIGH>", "impact": "<LOW|MEDIUM|HIGH>"}],
  "overall_score": <1-100>,
  "overall_sentiment": "<VERY_BEARISH|BEARISH|NEUTRAL|BULLISH|VERY_BULLISH>"
}"""


def market_analysis_agent(state: MultiAgentState) -> dict:
    """Run market analysis using news, sentiment, and on-chain data."""
    logger.info("[market_analysis] Starting...")
    macro = state.get("macro_context", {})
    rwa_universe = state.get("rwa_universe", [])

    # Fetch news data
    gdelt_rwa = fetch_gdelt_articles("RWA tokenization real world assets", 20, "7d")
    gdelt_crypto = fetch_gdelt_articles("cryptocurrency blockchain market", 20, "7d")
    gdelt_tone_rwa = fetch_gdelt_tone("RWA tokenization", "30d")
    gdelt_tone_crypto = fetch_gdelt_tone("cryptocurrency market", "30d")

    av_news = fetch_alpha_vantage_news(
        tickers="CRYPTO:BTC,CRYPTO:ETH",
        topics="blockchain,financial_markets",
        limit=15,
    )
    newsapi = fetch_newsapi_articles("RWA tokenization real world assets crypto", page_size=15)

    # Social data
    reddit = fetch_reddit_sentiment("cryptocurrency", "RWA real world assets", 15)
    bluesky = fetch_bluesky_posts("RWA tokenization crypto", 15)

    # On-chain data
    protocols = fetch_defillama_protocols(30)
    stables = fetch_defillama_stablecoins()
    gecko_ids = [a["gecko_id"] for a in rwa_universe if a.get("gecko_id")][:20]
    rwa_tokens = fetch_coingecko_market(gecko_ids) if gecko_ids else []
    dex_pools = fetch_gecko_terminal_pools("eth", 15)

    # Alpha Vantage sentiment aggregation
    av_scores = [a["overall_sentiment_score"] for a in av_news
                 if a.get("overall_sentiment_score")]
    avg_av_sentiment = sum(av_scores) / len(av_scores) if av_scores else 0

    data_context = {
        "macro_regime": macro.get("macro_regime", "UNKNOWN"),
        "rate_environment": macro.get("rate_environment", "UNKNOWN"),
        "gdelt_rwa_articles": [
            {"title": a["title"], "tone": a["tone"], "source": a["source"]}
            for a in gdelt_rwa[:12]
        ],
        "gdelt_crypto_articles": [
            {"title": a["title"], "tone": a["tone"]}
            for a in gdelt_crypto[:10]
        ],
        "gdelt_tones": {
            "rwa": gdelt_tone_rwa,
            "crypto": gdelt_tone_crypto,
        },
        "alpha_vantage": {
            "avg_sentiment": round(avg_av_sentiment, 3),
            "articles": [
                {"title": a["title"], "sentiment": a["overall_sentiment_label"]}
                for a in av_news[:8]
            ],
        },
        "newsapi_articles": [
            {"title": a["title"], "source": a["source"]}
            for a in newsapi[:8]
        ],
        "reddit_posts": [
            {"title": p["title"], "score": p["score"], "comments": p["num_comments"]}
            for p in reddit[:10]
        ],
        "bluesky_posts": [
            {"text": p["text"][:200], "likes": p["like_count"]}
            for p in bluesky[:10]
        ],
        "rwa_token_prices": [
            {"symbol": t["symbol"], "price": t["price"],
             "change_24h": t["change_24h"], "change_30d": t["change_30d"],
             "volume_24h": t["volume_24h"], "market_cap": t["market_cap"]}
            for t in rwa_tokens
        ],
        "stablecoin_mcap": stables.get("total_stablecoin_mcap", 0),
        "total_defi_tvl": sum(p["tvl"] or 0 for p in protocols),
        "rwa_total_tvl": sum(a["tvl"] for a in rwa_universe),
        "rwa_universe_count": len(rwa_universe),
        "top_dex_pools": [
            {"name": p["name"], "volume_24h": p["volume_24h"]}
            for p in dex_pools[:8]
        ],
    }

    prompt = (
        "Analyze the market sentiment and conditions for RWA investments:\n\n"
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
        logger.warning("[market_analysis] Failed to parse LLM response")
        analysis = {
            "overall_score": 50,
            "overall_sentiment": "NEUTRAL",
            "news_sentiment": {"score": 0, "label": "NEUTRAL", "summary": "Parse error"},
            "social_sentiment": {"score": 0, "label": "NEUTRAL", "summary": "Unavailable"},
            "market_momentum": {"trend": "SIDEWAYS", "summary": "Unavailable"},
            "onchain_signals": {"tvl_trend": "STABLE", "summary": "Unavailable"},
            "rwa_specific_signals": {"adoption_trend": "STEADY", "summary": "Unavailable"},
            "market_risks": [],
        }

    # Attach raw token data for downstream
    analysis["_raw_data"] = {
        "rwa_tokens": rwa_tokens,
        "protocols": protocols[:15],
    }

    logger.info(
        "[market_analysis] Done: score=%s sentiment=%s",
        analysis.get("overall_score"), analysis.get("overall_sentiment"),
    )

    return {"market_analysis": analysis}
