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

from bedrock_client import BedrockClient
from state import MultiAgentState

logger = logging.getLogger(__name__)
bedrock = BedrockClient()

FILTER_SYSTEM_PROMPT = """You are an Asset Analysis Agent performing the FINAL FILTER on RWA investment recommendations.

You are given matched RWA assets from a live universe (DefiLlama RWA protocols with real TVL data).
You must evaluate each asset against strict criteria and produce a final recommendation.

FILTER CRITERIA:
1. LEGAL/REGULATORY: Is the asset type likely legal in the customer's region? Flag if uncertain.
2. YIELD SUSTAINABILITY: Based on the asset type (treasury, credit, real estate, etc.), is the expected yield realistic?
3. REDEMPTION COMPATIBILITY: Does the asset type's typical redemption match the customer's needs?
4. SIZE/MATURITY: TVL > $10M is better. Audited protocols preferred. Multi-chain = more accessible.
5. CONCENTRATION RISK: Don't put more than 30% in a single asset or 50% in a single asset type.
6. SMART CONTRACT RISK: Consider audit count, TVL stability (change_7d), and protocol maturity.

For each asset, apply a PASS/FLAG/FAIL verdict:
- PASS: Meets all criteria, include in final recommendation
- FLAG: Has minor concerns, include with warnings
- FAIL: Does not meet criteria, exclude from recommendation

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
      "allocation_pct": <float>,
      "allocation_usd": <float>,
      "estimated_apy": <float>,
      "projected_return_usd": <float>,
      "legal_check": {"status": "<PASS|FLAG|FAIL>", "notes": "<string>"},
      "yield_check": {"status": "<PASS|FLAG|FAIL>", "sustainable": <bool>, "notes": "<string>"},
      "redemption_check": {"status": "<PASS|FLAG|FAIL>", "notes": "<string>"},
      "risk_check": {"status": "<PASS|FLAG|FAIL>", "notes": "<string>"},
      "warnings": [<strings>],
      "recommendation": "<STRONG_BUY|BUY|HOLD|AVOID>"
    }
  ],
  "portfolio_summary": {
    "total_investment": <float>,
    "projected_annual_return_pct": <float>,
    "projected_annual_return_usd": <float>,
    "risk_level": "<CONSERVATIVE|MODERATE|AGGRESSIVE>",
    "diversification": "<GOOD|MODERATE|POOR>",
    "assets_passed": <int>,
    "assets_flagged": <int>,
    "assets_failed": <int>
  },
  "key_warnings": [<strings>],
  "final_recommendation": "<string>"
}"""


def asset_analysis_agent(state: MultiAgentState) -> dict:
    """Apply final legal/regulatory/yield/redemption filters on live RWA assets."""
    logger.info("[asset_analysis] Starting final filter...")

    matched = state.get("matched_assets", [])
    customer = state.get("customer_profile", {})
    macro = state.get("macro_context", {})
    asset_class = state.get("asset_class_analysis", {})
    geopolitical = state.get("geopolitical_analysis", {})

    if not matched:
        return {
            "filtered_assets": [],
            "result": "No assets matched your profile. Consider adjusting your parameters.",
        }

    budget = customer.get("budget", 10000)

    # Get diversification recommendations if available
    recommended_mix = asset_class.get("recommended_mix", [])
    mix_map = {}
    for r in recommended_mix:
        key = r.get("slug") or r.get("token_id") or r.get("name", "")
        if key:
            mix_map[key] = r.get("allocation_pct", 0)

    # Build matched assets with allocation info
    matched_for_llm = []
    for a in matched[:12]:
        slug = a.get("slug", "")
        alloc_pct = mix_map.get(slug, a.get("suggested_allocation_pct", 10))
        alloc_usd = round(budget * alloc_pct / 100, 2)
        matched_for_llm.append({
            "slug": slug,
            "name": a.get("name"),
            "symbol": a.get("symbol"),
            "asset_type": a.get("asset_type"),
            "tvl": a.get("tvl"),
            "chain": a.get("chain", ""),
            "match_score": a.get("match_score"),
            "estimated_apy_range": a.get("estimated_apy_range", ""),
            "suggested_allocation_pct": alloc_pct,
            "allocation_usd": alloc_usd,
            "gecko_id": a.get("gecko_id", ""),
            "warnings": a.get("warnings", []),
        })

    data_context = {
        "customer_profile": customer,
        "macro_context": {
            "regime": macro.get("macro_regime", "UNKNOWN"),
            "rate_env": macro.get("rate_environment", "UNKNOWN"),
            "rwa_attractiveness": macro.get("rwa_attractiveness_label", "NEUTRAL"),
            "risk_free_rate": macro.get("key_rates", {}).get("yield_3m", 4.0),
        },
        "geopolitical_risk": geopolitical.get("overall_risk_level", "MEDIUM"),
        "regulatory_outlook": geopolitical.get("regulatory_landscape", {}),
        "matched_assets": matched_for_llm,
        "diversification_score": asset_class.get("diversification_score", 50),
    }

    prompt = (
        "Apply the final investment filter to these matched RWA assets:\n\n"
        f"{json.dumps(data_context, indent=2, default=str)}"
    )

    raw = bedrock.send_message(prompt, system_prompt=FILTER_SYSTEM_PROMPT)

    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("[asset_analysis] Failed to parse LLM response")
        result = _rule_based_filter(matched, customer, macro)

    filtered = result.get("filtered_assets", [])
    summary = result.get("portfolio_summary", {})
    recommendation = result.get("final_recommendation", "")

    output_lines = _format_final_output(filtered, summary, recommendation, customer, result)

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
    budget = customer.get("budget", 10000)
    filtered = []
    for a in matched[:10]:
        alloc_pct = a.get("suggested_allocation_pct", 10)
        alloc_usd = budget * alloc_pct / 100
        # Estimate APY from range string or default
        est_apy = 5.0
        apy_range = a.get("estimated_apy_range", "")
        if apy_range:
            try:
                nums = [float(x.strip('%')) for x in apy_range.replace('%', '').split('-') if x.strip()]
                est_apy = sum(nums) / len(nums) if nums else 5.0
            except (ValueError, ZeroDivisionError):
                pass
        projected = round(alloc_usd * est_apy / 100, 2)
        filtered.append({
            "slug": a.get("slug", ""),
            "name": a.get("name", ""),
            "symbol": a.get("symbol", ""),
            "asset_type": a.get("asset_type", ""),
            "tvl": a.get("tvl", 0),
            "chain": a.get("chain", ""),
            "verdict": "PASS" if a.get("match_score", 0) >= 50 else "FLAG",
            "allocation_pct": alloc_pct,
            "allocation_usd": round(alloc_usd, 2),
            "estimated_apy": est_apy,
            "projected_return_usd": projected,
            "warnings": a.get("warnings", []),
            "recommendation": "BUY" if a.get("match_score", 0) >= 60 else "HOLD",
        })
    total = sum(f["allocation_usd"] for f in filtered)
    avg_return = sum(
        f["estimated_apy"] * f["allocation_pct"] for f in filtered
    ) / 100 if filtered else 0
    return {
        "filtered_assets": filtered,
        "portfolio_summary": {
            "total_investment": total,
            "projected_annual_return_pct": round(avg_return, 2),
            "projected_annual_return_usd": round(total * avg_return / 100, 2),
            "assets_passed": sum(1 for f in filtered if f["verdict"] == "PASS"),
            "assets_flagged": sum(1 for f in filtered if f["verdict"] == "FLAG"),
            "assets_failed": 0,
        },
        "key_warnings": [],
        "final_recommendation": "Diversified RWA portfolio based on your profile.",
    }


def _format_final_output(filtered: list, summary: dict,
                          recommendation: str, customer: dict,
                          full_result: dict) -> list:
    """Format the final output for the user."""
    budget = customer.get("budget", 10000)
    lines = [
        "## RWA Investment Recommendation",
        "",
        f"**Budget:** ${budget:,.0f}",
        f"**Risk Tolerance:** {customer.get('risk_tolerance', 'moderate').title()}",
        f"**Time Horizon:** {customer.get('time_horizon_months', 12)} months",
        f"**Target Return:** {customer.get('expected_return_pct', 10)}%",
        f"**Redemption Need:** {customer.get('redemption_window', 'monthly').title()}",
        "",
    ]

    if summary:
        proj_return = summary.get("projected_annual_return_pct", 0)
        proj_usd = summary.get("projected_annual_return_usd", 0)
        lines.extend([
            "### Portfolio Summary",
            f"**Projected Return:** {proj_return:.1f}% (${proj_usd:,.0f}/yr)",
            f"**Risk Level:** {summary.get('risk_level', 'N/A')}",
            f"**Diversification:** {summary.get('diversification', 'N/A')}",
            "",
        ])

    lines.append("### Recommended Allocations")
    lines.append("")
    for i, asset in enumerate(filtered, 1):
        verdict = asset.get("verdict", "PASS")
        verdict_icon = {"PASS": "[PASS]", "FLAG": "[FLAG]", "FAIL": "[FAIL]"}.get(verdict, "?")
        reco = asset.get("recommendation", "HOLD")
        reco_icon = {"STRONG_BUY": "[STRONG BUY]", "BUY": "[BUY]",
                     "HOLD": "[HOLD]", "AVOID": "[AVOID]"}.get(reco, "")

        tvl = asset.get("tvl", 0)
        tvl_str = f"${tvl/1e6:.0f}M" if tvl >= 1e6 else f"${tvl/1e3:.0f}K"

        lines.append(
            f"**#{i} {asset.get('name', '?')}** ({asset.get('symbol', '?')}) "
            f"{verdict_icon} {reco_icon}"
        )
        lines.append(
            f"   Type: {asset.get('asset_type', '?')} | "
            f"Chain: {asset.get('chain', '?')} | TVL: {tvl_str}"
        )
        lines.append(
            f"   Allocation: ${asset.get('allocation_usd', 0):,.0f} "
            f"({asset.get('allocation_pct', 0):.1f}%) | "
            f"Est. APY: {asset.get('estimated_apy', 0):.1f}% | "
            f"Projected: ${asset.get('projected_return_usd', 0):,.0f}/yr"
        )
        warnings = asset.get("warnings", [])
        for w in warnings[:2]:
            lines.append(f"   Warning: {w}")
        lines.append("")

    key_warnings = full_result.get("key_warnings", [])
    if key_warnings:
        lines.append("### Key Warnings")
        for w in key_warnings:
            lines.append(f"- {w}")
        lines.append("")

    if recommendation:
        lines.append("### Final Recommendation")
        lines.append(recommendation)

    return lines
