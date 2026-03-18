"""
Asset Analysis Agent (Final Filter)
=====================================
Acts as the final filter in the pipeline. Evaluates each matched asset
against legal, regulatory, yield sustainability, and redemption criteria.

Works with the LIVE RWA universe — no hardcoded asset lists.
Produces the final filtered + ranked list of recommended assets with
concrete allocation amounts.
"""

import json
import logging
from agents.utils import extract_json

from bedrock_client import BedrockClient
from state import MultiAgentState

logger = logging.getLogger(__name__)
bedrock = BedrockClient()

FILTER_SYSTEM_PROMPT = """You are an Asset Analysis Agent performing the FINAL FILTER on RWA assets.

You are given matched RWA assets plus live market signals: news headlines, social posts, financial ratios, and on-chain data.

FILTER CRITERIA:
1. LEGAL/REGULATORY: Is the asset type likely legal in the customer's region? Flag if uncertain.
2. YIELD SUSTAINABILITY: Based on asset type, is the expected yield realistic?
3. REDEMPTION COMPATIBILITY: Does the asset type's typical redemption match the customer's needs?
4. SIZE/MATURITY: TVL > $10M preferred. Multi-chain = more accessible.
5. CONCENTRATION RISK: Max 30% single asset, 50% single asset type.
6. SMART CONTRACT RISK: Consider audit count, TVL stability (change_7d), protocol maturity.

For each asset, apply a PASS/FLAG/FAIL verdict:
- PASS: Meets all criteria
- FLAG: Minor concerns, include with notes
- FAIL: Does not meet criteria, exclude

For each asset, include qualitative_factors: draw on the provided news headlines, social posts, sanctions context, GDELT tones, financial ratios (NFCI, yield curve, stablecoin mcap), and on-chain signals to explain WHY this specific asset is included or excluded. Be specific — cite actual data points from the signals provided.

IMPORTANT: Keep all text fields under 30 words. Be concise.

Return ONLY valid JSON:
{
  "filtered_assets": [
    {
      "slug": "<string>",
      "name": "<string>",
      "symbol": "<string>",
      "asset_type": "<string>",
      "tvl": <float>,
      "chain": "<string>",
      "verdict": "<PASS|FLAG|FAIL>",
      "warnings": ["<string>"],
      "recommendation": "<STRONG_BUY|BUY|HOLD|AVOID>",
      "qualitative_factors": {
        "macro_fit": "<how macro regime/rates support or challenge this asset>",
        "news_signal": "<relevant news headline or social post that supports/challenges this asset>",
        "regulatory_signal": "<regulatory or sanctions context specific to this asset/region>",
        "onchain_signal": "<TVL trend, DeFi yield competition, or on-chain metric relevant to this asset>"
      }
    }
  ],
  "portfolio_summary": {
    "risk_level": "<CONSERVATIVE|MODERATE|AGGRESSIVE>",
    "diversification": "<GOOD|MODERATE|POOR>",
    "assets_passed": <int>,
    "assets_flagged": <int>,
    "assets_failed": <int>
  },
  "key_warnings": ["<string>"],
  "final_recommendation": "<string>"
}"""


def asset_analysis_agent(state: MultiAgentState) -> dict:
    """Apply final legal/regulatory/yield/redemption filters on live RWA assets."""
    logger.info("[asset_analysis] Starting final filter...")

    matched = state.get("matched_assets", [])
    customer = state.get("customer_profile", {})
    macro = state.get("macro_context", {})
    asset_class = state.get("asset_class_analysis", {})
    industry = state.get("industry_analysis", {})
    financial = state.get("financial_analysis", {})
    cashflow = state.get("cashflow_analysis", {})
    geopolitical = state.get("geopolitical_analysis", {})
    market = state.get("market_analysis", {})

    if not matched:
        logger.error("[asset_analysis] matched_assets is empty — check match_asset logs for root cause")
        return {
            "filtered_assets": [],
            "result": "Analysis incomplete — no assets were matched. Please check the logs for details and try again.",
        }

    # Build matched assets for LLM
    matched_for_llm = []
    for a in matched[:12]:
        matched_for_llm.append({
            "slug": a.get("slug", ""),
            "name": a.get("name"),
            "symbol": a.get("symbol"),
            "asset_type": a.get("asset_type"),
            "tvl": a.get("tvl"),
            "chain": a.get("chain", ""),
            "match_score": a.get("match_score"),
            "gecko_id": a.get("gecko_id", ""),
            "change_7d": a.get("change_7d"),
            "audits": a.get("audits", 0),
        })

    reg_landscape = geopolitical.get("regulatory_landscape", {})
    geo_signals = geopolitical.get("_key_signals", {})
    fin_raw = financial.get("_raw_data", {})
    cf_signals = cashflow.get("_key_signals", {})
    mkt_raw = market.get("_raw_data", {})

    data_context = {
        "customer_profile": {
            "risk_tolerance": customer.get("risk_tolerance"),
            "expected_return_pct": customer.get("expected_return_pct"),
            "time_horizon_months": customer.get("time_horizon_months"),
            "redemption_frequency": customer.get("redemption_frequency"),
            "region": customer.get("region"),
        },
        "macro_context": {
            "regime": macro.get("macro_regime", "UNKNOWN"),
            "rate_env": macro.get("rate_environment", "UNKNOWN"),
            "rwa_attractiveness": macro.get("rwa_attractiveness_label", "NEUTRAL"),
            "yield_3m": macro.get("key_rates", {}).get("yield_3m", 4.0),
            "yield_10y": macro.get("key_rates", {}).get("yield_10y"),
            "yield_30y": macro.get("key_rates", {}).get("yield_30y"),
        },
        "market_signals": {
            "geopolitical_risk": geopolitical.get("overall_risk_level", "MEDIUM"),
            "regulatory_summary": reg_landscape.get("summary", "") if isinstance(reg_landscape, dict) else str(reg_landscape)[:200],
            "sanctions_summary": geopolitical.get("sanctions_risk", {}).get("summary", ""),
            "gdelt_top_news": geo_signals.get("gdelt_top_articles", [])[:4],
            "gdelt_tones": geo_signals.get("gdelt_tones", {}),
            "social_posts": geo_signals.get("reddit_top", [])[:3],
            "nfci": fin_raw.get("nfci"),
            "stablecoin_mcap_B": round(fin_raw.get("stablecoins", {}).get("total_stablecoin_mcap", 0) / 1e9, 1),
            "avg_defi_yield_pct": cf_signals.get("avg_defi_yield"),
            "avg_rwa_yield_pct": cf_signals.get("avg_rwa_yield"),
            "rwa_token_prices": [
                {"symbol": t["symbol"], "price": t.get("price"), "change_24h": t.get("change_24h")}
                for t in mkt_raw.get("rwa_tokens", [])[:5]
            ],
        },
        "matched_assets": matched_for_llm,
        "diversification_score": asset_class.get("diversification_score", 50),
    }

    prompt = (
        "Apply the final investment filter to these matched RWA assets:\n\n"
        f"{json.dumps(data_context, default=str)}"
    )

    logger.info("[asset_analysis] Sending %d assets to LLM for final filtering...", len(matched_for_llm))
    try:
        raw = bedrock.send_message(prompt, system_prompt=FILTER_SYSTEM_PROMPT)
        logger.info("[asset_analysis] LLM response received, parsing...")
        result = extract_json(raw)
    except Exception as e:
        logger.warning("[asset_analysis] LLM call failed (%s), using rule-based fallback", e)
        result = _rule_based_filter(matched, customer, macro)

    filtered = result.get("filtered_assets", [])
    summary = result.get("portfolio_summary", {})
    recommendation = result.get("final_recommendation", "")

    analysis_context = {
        "industry": industry,
        "financial": financial,
        "cashflow": cashflow,
        "geopolitical": geopolitical,
        "market": market,
    }
    output_lines = _format_final_output(filtered, summary, recommendation, customer, result, analysis_context)

    logger.info(
        "[asset_analysis] Done: %d passed, %d flagged, %d failed",
        summary.get("assets_passed", 0),
        summary.get("assets_flagged", 0),
        summary.get("assets_failed", 0),
    )

    return {
        "filtered_assets": filtered,
        "result": "\n".join(output_lines),
    }


def _rule_based_filter(matched: list, customer: dict, macro: dict) -> dict:
    """Fallback rule-based filtering if LLM fails."""
    filtered = []
    for a in matched[:10]:
        filtered.append({
            "slug": a.get("slug", ""),
            "name": a.get("name", ""),
            "symbol": a.get("symbol", ""),
            "asset_type": a.get("asset_type", ""),
            "tvl": a.get("tvl", 0),
            "chain": a.get("chain", ""),
            "verdict": "PASS" if a.get("match_score", 0) >= 50 else "FLAG",
            "warnings": a.get("warnings", []),
            "recommendation": "BUY" if a.get("match_score", 0) >= 60 else "HOLD",
        })
    return {
        "filtered_assets": filtered,
        "portfolio_summary": {
            "assets_passed": sum(1 for f in filtered if f["verdict"] == "PASS"),
            "assets_flagged": sum(1 for f in filtered if f["verdict"] == "FLAG"),
            "assets_failed": 0,
        },
        "key_warnings": [],
        "final_recommendation": "RWA asset analysis based on your profile.",
    }


def _format_final_output(filtered: list, summary: dict,
                          recommendation: str, customer: dict,
                          full_result: dict, analysis_context: dict = None) -> list:
    """Format the final output for the user."""
    lines = [
        "## RWA Asset Analysis",
        "",
        f"**Risk Tolerance:** {customer.get('risk_tolerance', 'moderate').title()}",
        f"**Time Horizon:** {customer.get('time_horizon_months', 12)} months",
        f"**Target Return:** {customer.get('expected_return_pct', 10)}%",
        f"**Redemption Need:** {customer.get('redemption_window', 'monthly').title()}",
        "",
    ]

    # --- Analysis Overview from the 5 parallel agents ---
    if analysis_context:
        lines.append("### Analysis Overview")
        lines.append("")

        ind = analysis_context.get("industry", {})
        if ind:
            outlook = ind.get("overall_outlook", "N/A")
            score = ind.get("overall_score", "N/A")
            sector = ind.get("sector_growth", {})
            rates = ind.get("rates_backdrop", {})
            liquidity = ind.get("liquidity_assessment", {})
            raw = ind.get("_raw_data", {})
            lines.append(f"**Industry Analysis** — Score: {score}/100, Outlook: {outlook}")
            if sector.get("summary"):
                lines.append(f"  - Sector Growth: {sector['summary']}")
            if rates.get("summary"):
                lines.append(f"  - Rates Backdrop: {rates['summary']}")
            if liquidity.get("summary"):
                lines.append(f"  - Liquidity: {liquidity['summary']}")
            # Surface top protocol data points
            top_protocols = raw.get("protocols", [])[:3]
            if top_protocols:
                proto_str = ", ".join(
                    f"{p['name']} (TVL ${p['tvl']/1e9:.1f}B)" if p.get("tvl", 0) >= 1e9
                    else f"{p['name']} (TVL ${p['tvl']/1e6:.0f}M)"
                    for p in top_protocols if p.get("tvl")
                )
                if proto_str:
                    lines.append(f"  - Top Protocols: {proto_str}")
            risks = ind.get("industry_risks", [])
            if risks:
                lines.append(f"  - Key Risks: {'; '.join(risks[:2])}")
            lines.append("")

        fin = analysis_context.get("financial", {})
        if fin:
            assessment = fin.get("overall_assessment", "N/A")
            score = fin.get("overall_score", "N/A")
            conditions = fin.get("financial_conditions", {})
            spreads = fin.get("spread_analysis", {})
            stables = fin.get("stablecoin_liquidity", {})
            funding = fin.get("funding_environment", {})
            raw = fin.get("_raw_data", {})
            lines.append(f"**Financial Analysis** — Score: {score}/100, Assessment: {assessment}")
            if conditions.get("summary"):
                lines.append(f"  - Financial Conditions: {conditions['summary']}")
            # Surface NFCI and stablecoin mcap
            nfci = raw.get("nfci")
            if nfci is not None:
                lines.append(f"  - NFCI Index: {nfci} (negative = loose conditions, positive = tight)")
            stable_data = raw.get("stablecoins", {})
            stable_mcap = stable_data.get("total_stablecoin_mcap", 0)
            if stable_mcap:
                lines.append(f"  - Stablecoin Market Cap: ${stable_mcap/1e9:.0f}B (on-chain liquidity pool)")
            if spreads.get("summary"):
                lines.append(f"  - Spread Analysis: {spreads['summary']}")
            if funding.get("summary"):
                lines.append(f"  - Funding Environment: {funding['summary']}")
            # Top DeFi yields for context
            top_yields = raw.get("defi_yields", [])[:3]
            if top_yields:
                yield_str = ", ".join(
                    f"{y['project']} {y['apy']:.1f}%" for y in top_yields if y.get("apy")
                )
                if yield_str:
                    lines.append(f"  - Benchmark DeFi Yields: {yield_str}")
            lines.append("")

        cf = analysis_context.get("cashflow", {})
        if cf:
            assessment = cf.get("overall_assessment", "N/A")
            score = cf.get("overall_score", "N/A")
            discount = cf.get("discount_rate_analysis", {})
            yield_comp = cf.get("yield_competition", {})
            growth = cf.get("product_growth", {})
            cf_risks = cf.get("cashflow_risks", [])
            signals = cf.get("_key_signals", {})
            lines.append(f"**Cash Flow Analysis** — Score: {score}/100, Assessment: {assessment}")
            # Surface actual yield numbers
            y3m = signals.get("yield_3m")
            y10y = signals.get("yield_10y")
            avg_defi = signals.get("avg_defi_yield")
            avg_rwa = signals.get("avg_rwa_yield")
            if y3m and y10y:
                lines.append(f"  - Risk-Free Rates: 3M Treasury {y3m:.2f}% | 10Y Treasury {y10y:.2f}%")
            if avg_defi and avg_rwa:
                lines.append(f"  - Yield Comparison: Avg DeFi {avg_defi:.1f}% vs Avg RWA {avg_rwa:.1f}% — RWA premium of {avg_rwa - avg_defi:.1f}%")
            if discount.get("summary"):
                lines.append(f"  - Discount Rates: {discount['summary']}")
            if growth.get("summary"):
                lines.append(f"  - Product Growth: {growth['summary']}")
            # Top competing DeFi yields
            top_defi = signals.get("top_defi_yields", [])[:3]
            if top_defi:
                defi_str = ", ".join(f"{y['protocol']} {y['apy']:.1f}%" for y in top_defi if y.get("apy"))
                if defi_str:
                    lines.append(f"  - Competing DeFi Yields: {defi_str}")
            if cf_risks:
                lines.append(f"  - Cash Flow Risks: {'; '.join(cf_risks[:2])}")
            lines.append("")

        geo = analysis_context.get("geopolitical", {})
        if geo:
            risk_level = geo.get("overall_risk_level", "N/A")
            score = geo.get("overall_score", "N/A")
            reg = geo.get("regulatory_landscape", {})
            policy = geo.get("policy_trends", {})
            sanctions = geo.get("sanctions_risk", {})
            signals = geo.get("_key_signals", {})
            lines.append(f"**Geopolitical Analysis** — Score: {score}/100, Risk: {risk_level}")
            if reg.get("summary"):
                lines.append(f"  - Regulatory Landscape: {reg['summary']}")
            if policy.get("summary"):
                lines.append(f"  - Policy Trends: {policy['summary']}")
            if sanctions.get("summary"):
                lines.append(f"  - Sanctions Risk: {sanctions['summary']}")
            # Surface GDELT news headlines
            gdelt_articles = signals.get("gdelt_top_articles", [])[:3]
            if gdelt_articles:
                lines.append("  - Recent News:")
                for art in gdelt_articles:
                    tone = art.get("tone", 0)
                    tone_label = "positive" if tone > 1 else ("negative" if tone < -1 else "neutral")
                    lines.append(f"    • [{tone_label}] {art['title'][:100]} ({art.get('source', '')})")
            # GDELT tone scores
            tones = signals.get("gdelt_tones", {})
            if tones:
                tone_summary = "; ".join(
                    f"{q[:20]}: {v.get('avg_tone', 'N/A')}" for q, v in list(tones.items())[:2]
                )
                lines.append(f"  - GDELT Tone Scores: {tone_summary}")
            # Reddit signals
            reddit_top = signals.get("reddit_top", [])
            if reddit_top:
                lines.append(f"  - Social Signal: \"{reddit_top[0][:100]}\"")
            lines.append("")

        mkt = analysis_context.get("market", {})
        if mkt:
            sentiment = mkt.get("overall_sentiment", "N/A")
            score = mkt.get("overall_score", "N/A")
            news = mkt.get("news_sentiment", {})
            momentum = mkt.get("market_momentum", {})
            onchain = mkt.get("onchain_signals", {})
            rwa_signals = mkt.get("rwa_specific_signals", {})
            raw = mkt.get("_raw_data", {})
            lines.append(f"**Market Analysis** — Score: {score}/100, Sentiment: {sentiment}")
            if news.get("summary"):
                lines.append(f"  - News Sentiment: {news['summary']}")
            if momentum.get("summary"):
                lines.append(f"  - Market Momentum: {momentum['summary']}")
            if onchain.get("summary"):
                lines.append(f"  - On-Chain Signals: {onchain['summary']}")
            # Surface specific RWA token prices
            rwa_tokens = raw.get("rwa_tokens", [])[:3]
            if rwa_tokens:
                token_str = ", ".join(
                    f"{t['symbol']} ${t['price']:.2f} ({t.get('change_24h', 0):+.1f}% 24h)"
                    for t in rwa_tokens if t.get("price")
                )
                if token_str:
                    lines.append(f"  - RWA Token Prices: {token_str}")
            if rwa_signals.get("summary"):
                lines.append(f"  - RWA Signals: {rwa_signals['summary']}")
            mkt_risks = mkt.get("market_risks", [])
            if mkt_risks:
                risk_strs = [r["risk"] if isinstance(r, dict) else str(r) for r in mkt_risks[:2]]
                lines.append(f"  - Key Risks: {'; '.join(risk_strs)}")
            lines.append("")

    if summary:
        lines.extend([
            "### Overview",
            f"**Risk Level:** {summary.get('risk_level', 'N/A')}",
            f"**Diversification:** {summary.get('diversification', 'N/A')}",
            "",
        ])

    lines.append("### Asset Breakdown")
    lines.append("")
    signal_map = {
        "STRONG_BUY": "[STRONG INCLUSION]",
        "BUY": "[INCLUSION]",
        "HOLD": "[NEUTRAL]",
        "AVOID": "[EXCLUSION]",
    }
    for i, asset in enumerate(filtered, 1):
        verdict = asset.get("verdict", "PASS")
        verdict_icon = {"PASS": "[PASS]", "FLAG": "[FLAG]", "FAIL": "[FAIL]"}.get(verdict, "?")
        signal = signal_map.get(asset.get("recommendation", "HOLD"), "")

        tvl = asset.get("tvl", 0)
        tvl_str = f"${tvl/1e6:.0f}M" if tvl >= 1e6 else f"${tvl/1e3:.0f}K"

        lines.append(
            f"**#{i} {asset.get('name', '?')}** ({asset.get('symbol', '?')}) "
            f"{verdict_icon} {signal}"
        )
        lines.append(
            f"   Type: {asset.get('asset_type', '?')} | "
            f"Chain: {asset.get('chain', '?')} | TVL: {tvl_str}"
        )
        # Qualitative factors
        qf = asset.get("qualitative_factors", {})
        if qf.get("macro_fit"):
            lines.append(f"   Macro: {qf['macro_fit']}")
        if qf.get("news_signal"):
            lines.append(f"   News/Social: {qf['news_signal']}")
        if qf.get("regulatory_signal"):
            lines.append(f"   Regulatory: {qf['regulatory_signal']}")
        if qf.get("onchain_signal"):
            lines.append(f"   On-Chain: {qf['onchain_signal']}")
        warnings = asset.get("warnings", [])
        for w in warnings[:2]:
            lines.append(f"   Note: {w}")
        lines.append("")

    key_warnings = full_result.get("key_warnings", [])
    if key_warnings:
        lines.append("### Key Considerations")
        for w in key_warnings:
            lines.append(f"- {w}")
        lines.append("")

    if recommendation:
        lines.append("### Summary")
        lines.append(recommendation)

    return lines
