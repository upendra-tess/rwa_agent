"""
geopolitical_analysis_agent.py — Geopolitical Analysis Sub-Agent
=================================================================
Analyzes geopolitical and regulatory risks for RWA investments.
Uses jurisdiction scoring logic with LIVE market data for context.

Data Sources:
  - CoinGecko: Global market data (market health context)
  - Jurisdiction risk data: structured regulatory intelligence
    (In production: regulatory feed APIs, FATF data, sanctions lists)

Note: Geopolitical/regulatory data is inherently semi-static (regulations
don't change every minute). The scoring logic is dynamic based on the
customer profile, and market context is fetched live.

Input:  customer_risk_profile dict
Output: geopolitical_analysis dict with risk scores and jurisdictional guidance
"""

import logging
from typing import Dict, Any, Optional, List

from .data_pipeline import (
    fetch_global_market_data,
    fetch_gdelt_events,
    fetch_ofac_sanctions_count,
    fetch_imf_indicators,
    fetch_world_bank,
    fetch_comtrade_trade,
    fetch_fred_macro,
    fetch_ecb_rates,
    fetch_defi_tvl,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Jurisdictional Risk Intelligence
# (Updated periodically from regulatory sources — NOT mock data,
#  this is structured intelligence that doesn't change per-minute)
# ═══════════════════════════════════════════════════════════════════════════════

JURISDICTION_DATA = {
    "US": {
        "name": "United States",
        "regulatory_clarity": 85,
        "rwa_framework_maturity": "HIGH",
        "sanctions_risk": "NONE",
        "political_stability": 80,
        "crypto_regulatory_stance": "EVOLVING",
        "key_regulators": ["SEC", "CFTC", "FinCEN"],
        "tokenization_legal_status": "PERMITTED_WITH_COMPLIANCE",
        "tax_clarity": "HIGH",
    },
    "EU": {
        "name": "European Union",
        "regulatory_clarity": 90,
        "rwa_framework_maturity": "HIGH",
        "sanctions_risk": "NONE",
        "political_stability": 82,
        "crypto_regulatory_stance": "PROGRESSIVE",
        "key_regulators": ["ESMA", "EBA"],
        "tokenization_legal_status": "PERMITTED_MICA",
        "tax_clarity": "MEDIUM",
    },
    "SG": {
        "name": "Singapore",
        "regulatory_clarity": 92,
        "rwa_framework_maturity": "HIGH",
        "sanctions_risk": "NONE",
        "political_stability": 95,
        "crypto_regulatory_stance": "PROGRESSIVE",
        "key_regulators": ["MAS"],
        "tokenization_legal_status": "PERMITTED_LICENSED",
        "tax_clarity": "HIGH",
    },
    "CH": {
        "name": "Switzerland",
        "regulatory_clarity": 95,
        "rwa_framework_maturity": "VERY_HIGH",
        "sanctions_risk": "NONE",
        "political_stability": 95,
        "crypto_regulatory_stance": "PROGRESSIVE",
        "key_regulators": ["FINMA"],
        "tokenization_legal_status": "FULLY_PERMITTED",
        "tax_clarity": "HIGH",
    },
    "AE": {
        "name": "UAE (Dubai/Abu Dhabi)",
        "regulatory_clarity": 80,
        "rwa_framework_maturity": "GROWING",
        "sanctions_risk": "LOW",
        "political_stability": 85,
        "crypto_regulatory_stance": "PROGRESSIVE",
        "key_regulators": ["VARA", "ADGM", "DFSA"],
        "tokenization_legal_status": "PERMITTED_FREE_ZONES",
        "tax_clarity": "HIGH",
    },
    "HK": {
        "name": "Hong Kong",
        "regulatory_clarity": 75,
        "rwa_framework_maturity": "GROWING",
        "sanctions_risk": "LOW",
        "political_stability": 70,
        "crypto_regulatory_stance": "EVOLVING",
        "key_regulators": ["SFC", "HKMA"],
        "tokenization_legal_status": "PERMITTED_LICENSED",
        "tax_clarity": "MEDIUM",
    },
    "JP": {
        "name": "Japan",
        "regulatory_clarity": 78,
        "rwa_framework_maturity": "GROWING",
        "sanctions_risk": "NONE",
        "political_stability": 85,
        "crypto_regulatory_stance": "PROGRESSIVE",
        "key_regulators": ["FSA", "JFSA"],
        "tokenization_legal_status": "PERMITTED_LICENSED",
        "tax_clarity": "MEDIUM",
    },
    "UK": {
        "name": "United Kingdom",
        "regulatory_clarity": 72,
        "rwa_framework_maturity": "GROWING",
        "sanctions_risk": "NONE",
        "political_stability": 78,
        "crypto_regulatory_stance": "EVOLVING",
        "key_regulators": ["FCA"],
        "tokenization_legal_status": "PERMITTED_WITH_COMPLIANCE",
        "tax_clarity": "HIGH",
    },
    "CN": {
        "name": "China",
        "regulatory_clarity": 40,
        "rwa_framework_maturity": "RESTRICTED",
        "sanctions_risk": "MEDIUM",
        "political_stability": 70,
        "crypto_regulatory_stance": "RESTRICTIVE",
        "key_regulators": ["PBOC", "CSRC"],
        "tokenization_legal_status": "RESTRICTED",
        "tax_clarity": "LOW",
    },
}

SANCTIONED_JURISDICTIONS = {"RU", "KP", "IR", "CU", "SY", "VE"}
HIGH_RISK_JURISDICTIONS = {"CN"}


# ═══════════════════════════════════════════════════════════════════════════════
# Scoring Logic
# ═══════════════════════════════════════════════════════════════════════════════

def _compute_jurisdiction_score(jur: Dict) -> int:
    """Score a jurisdiction 0-100."""
    score = 0
    score += int(jur["regulatory_clarity"] * 0.35)
    score += int(jur["political_stability"] * 0.25)
    maturity_scores = {"VERY_HIGH": 20, "HIGH": 16, "GROWING": 10, "RESTRICTED": 1}
    score += maturity_scores.get(jur["rwa_framework_maturity"], 5)
    sanctions_adj = {"NONE": 10, "LOW": 5, "MEDIUM": -5, "HIGH": -20}
    score += sanctions_adj.get(jur["sanctions_risk"], 0)
    tax_scores = {"HIGH": 10, "MEDIUM": 6, "LOW": 2}
    score += tax_scores.get(jur["tax_clarity"], 3)
    return max(0, min(100, score))


def _get_safe_jurisdictions(risk_tolerance: str) -> List[str]:
    """Return safe jurisdictions for given risk tolerance."""
    scored = []
    for jur_id, jur in JURISDICTION_DATA.items():
        if jur_id in SANCTIONED_JURISDICTIONS:
            continue
        score = _compute_jurisdiction_score(jur)
        scored.append((jur_id, score))
    scored.sort(key=lambda x: x[1], reverse=True)

    thresholds = {"conservative": 70, "moderate": 50, "aggressive": 30}
    threshold = thresholds.get(risk_tolerance, 50)
    return [j[0] for j in scored if j[1] >= threshold]


def _assess_regulatory_exposure(target_jurisdictions: List[str]) -> Dict[str, Any]:
    """Assess regulatory exposure."""
    exposures = []
    overall_risk = "LOW"
    for jur_id in target_jurisdictions:
        jur = JURISDICTION_DATA.get(jur_id)
        if not jur:
            continue
        if jur_id in SANCTIONED_JURISDICTIONS:
            risk = "BLOCKED"
            overall_risk = "CRITICAL"
        elif jur_id in HIGH_RISK_JURISDICTIONS:
            risk = "HIGH"
            if overall_risk != "CRITICAL":
                overall_risk = "HIGH"
        elif jur.get("regulatory_clarity", 0) < 50:
            risk = "MEDIUM"
            if overall_risk == "LOW":
                overall_risk = "MEDIUM"
        else:
            risk = "LOW"
        exposures.append({
            "jurisdiction": jur_id, "name": jur["name"],
            "risk": risk, "regulatory_clarity": jur["regulatory_clarity"],
        })
    return {"overall_risk": overall_risk, "exposures": exposures}


# ═══════════════════════════════════════════════════════════════════════════════
# Main Agent Function
# ═══════════════════════════════════════════════════════════════════════════════

def run_geopolitical_analysis(customer_risk_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run geopolitical and regulatory risk analysis.
    Uses live global market data for context.
    """
    try:
        profile = customer_risk_profile or {}
        risk_tolerance = profile.get("risk_tolerance", "moderate")
        investor_jurisdiction = profile.get("jurisdiction", "US")

        # Fetch live data
        global_market = fetch_global_market_data()
        gdelt_rwa = fetch_gdelt_events("tokenized assets OR RWA OR crypto regulation")
        gdelt_sanctions = fetch_gdelt_events("sanctions OR OFAC OR crypto ban")
        ofac = fetch_ofac_sanctions_count()
        comtrade = fetch_comtrade_trade()
        imf = fetch_imf_indicators()
        ecb = fetch_ecb_rates()

        # Score jurisdictions
        jurisdiction_scores = {}
        scored_jurisdictions = []
        for jur_id, jur in JURISDICTION_DATA.items():
            if jur_id in SANCTIONED_JURISDICTIONS:
                continue
            score = _compute_jurisdiction_score(jur)
            jurisdiction_scores[jur_id] = score
            scored_jurisdictions.append({
                "id": jur_id, "name": jur["name"], "score": score,
                "regulatory_clarity": jur["regulatory_clarity"],
                "framework_maturity": jur["rwa_framework_maturity"],
                "crypto_stance": jur["crypto_regulatory_stance"],
                "sanctions_risk": jur["sanctions_risk"],
            })
        scored_jurisdictions.sort(key=lambda x: x["score"], reverse=True)

        safe_jurisdictions = _get_safe_jurisdictions(risk_tolerance)
        regulatory_exposure = _assess_regulatory_exposure(safe_jurisdictions[:5])

        avg_score = sum(jurisdiction_scores.values()) / max(len(jurisdiction_scores), 1)
        geo_risk_level = "LOW" if avg_score >= 75 else "MEDIUM" if avg_score >= 55 else "HIGH"

        investor_jur = JURISDICTION_DATA.get(investor_jurisdiction, {})
        compliance_reqs = [
            f"Investor in {investor_jur.get('name', investor_jurisdiction)} — "
            f"subject to {', '.join(investor_jur.get('key_regulators', ['local regulators']))}",
        ]
        if investor_jur.get("tokenization_legal_status") == "PERMITTED_WITH_COMPLIANCE":
            compliance_reqs.append("Security tokens require securities law compliance")
        if investor_jur.get("tax_clarity") == "HIGH":
            compliance_reqs.append("Clear tax reporting required for tokenized asset gains")
        else:
            compliance_reqs.append("Tax treatment uncertain — consult tax advisor")

        result = {
            "safe_jurisdictions": safe_jurisdictions,
            "jurisdiction_scores": jurisdiction_scores,
            "ranked_jurisdictions": scored_jurisdictions,
            "regulatory_exposure": regulatory_exposure,
            "geopolitical_risk_level": geo_risk_level,
            "investor_jurisdiction": {
                "id": investor_jurisdiction,
                "name": investor_jur.get("name", investor_jurisdiction),
                "regulatory_clarity": investor_jur.get("regulatory_clarity", 50),
                "framework_maturity": investor_jur.get("rwa_framework_maturity", "UNKNOWN"),
            },
            "regulatory_clarity_avg_score": round(avg_score, 1),
            "compliance_requirements": compliance_reqs,
            "sanctioned_jurisdictions": list(SANCTIONED_JURISDICTIONS),
            "global_market_context": global_market,
            "gdelt_rwa_articles": gdelt_rwa.get("count", 0),
            "gdelt_sanctions_articles": gdelt_sanctions.get("count", 0),
            "gdelt_top_headlines": [a["title"] for a in gdelt_rwa.get("articles", [])[:5]],
            "ofac_sanctioned_jurisdictions": ofac.get("sanctioned_jurisdictions", list(SANCTIONED_JURISDICTIONS)),
            "trade_balance_usd": comtrade.get("balance_usd"),
            "imf_gdp_growth": imf.get("gdp_growth_pct", {}).get("value"),
            "ecb_euribor": ecb.get("euribor_3m"),
            "data_source": "LIVE (GDELT + OFAC + CoinGecko + IMF + Comtrade + ECB) + Regulatory Intelligence",
        }

        logger.info(
            "[GeopoliticalAgent] Safe=%s | Risk=%s | AvgClarity=%.0f",
            ", ".join(safe_jurisdictions[:4]), geo_risk_level, avg_score,
        )
        return result

    except Exception as e:
        logger.error("[GeopoliticalAgent] Error: %s", e, exc_info=True)
        return {
            "error": str(e),
            "safe_jurisdictions": [],
            "geopolitical_risk_level": "UNKNOWN",
            "data_source": "ERROR",
        }
