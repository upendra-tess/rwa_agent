"""
industry_analysis_agent.py — Industry Analysis Sub-Agent
=========================================================
Analyzes industry sectors relevant to the customer's risk profile
using LIVE data from CoinGecko and DeFiLlama.

Data Sources:
  - CoinGecko: RWA category tokens, market caps, volume
  - DeFiLlama: RWA protocols TVL, protocol growth rates

Input:  customer_risk_profile dict
Output: industry_analysis dict with sector scores and outlook
"""

import logging
from typing import Dict, Any, Optional, List

from .data_pipeline import (
    fetch_rwa_category_tokens,
    fetch_rwa_protocols,
    fetch_defi_tvl,
    fetch_global_market_data,
    fetch_fred_macro,
    fetch_gdpnow,
    fetch_imf_indicators,
    fetch_world_bank,
    fetch_ecb_rates,
)

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# Sector Classification (maps live data into sectors)
# ═══════════════════════════════════════════════════════════════════════════════

# Protocol → sector mapping for DeFiLlama protocols
PROTOCOL_SECTOR_MAP = {
    "ondo": "treasury_yield",
    "backed": "treasury_yield",
    "mountain": "treasury_yield",
    "openeden": "treasury_yield",
    "matrixdock": "treasury_yield",
    "maple": "private_credit",
    "goldfinch": "private_credit",
    "clearpool": "private_credit",
    "centrifuge": "real_estate",
    "realt": "real_estate",
    "lofty": "real_estate",
    "paxos": "commodities",
    "tether gold": "commodities",
    "aave": "defi_yield",
    "compound": "defi_yield",
    "lido": "defi_yield",
    "pendle": "defi_yield",
    "maker": "defi_yield",
}

SECTOR_METADATA = {
    "treasury_yield": {
        "name": "Treasury & Yield Products",
        "risk_level": "LOW",
        "regulatory_clarity": "HIGH",
    },
    "private_credit": {
        "name": "Private Credit & Lending",
        "risk_level": "MEDIUM",
        "regulatory_clarity": "MEDIUM",
    },
    "real_estate": {
        "name": "Real Estate (Tokenized)",
        "risk_level": "LOW",
        "regulatory_clarity": "HIGH",
    },
    "commodities": {
        "name": "Commodities (Gold, Carbon)",
        "risk_level": "MEDIUM",
        "regulatory_clarity": "MEDIUM",
    },
    "equities": {
        "name": "Tokenized Equities & Funds",
        "risk_level": "HIGH",
        "regulatory_clarity": "LOW",
    },
    "defi_yield": {
        "name": "DeFi Yield Strategies",
        "risk_level": "HIGH",
        "regulatory_clarity": "LOW",
    },
    "infrastructure": {
        "name": "Infrastructure & Utilities",
        "risk_level": "LOW",
        "regulatory_clarity": "MEDIUM",
    },
}

# Risk tolerance → which sectors to consider
RISK_SECTOR_MAP = {
    "conservative": ["treasury_yield", "real_estate", "infrastructure"],
    "moderate": ["treasury_yield", "real_estate", "private_credit", "commodities", "infrastructure"],
    "aggressive": ["private_credit", "commodities", "equities", "defi_yield", "treasury_yield", "real_estate"],
}


# ═══════════════════════════════════════════════════════════════════════════════
# Live Data Processing
# ═══════════════════════════════════════════════════════════════════════════════

def _classify_protocol_to_sector(protocol_name: str) -> str:
    """Classify a protocol into a sector based on its name."""
    name_lower = protocol_name.lower()
    for keyword, sector in PROTOCOL_SECTOR_MAP.items():
        if keyword in name_lower:
            return sector
    return "other"


def _build_sector_data_from_live(
    rwa_tokens: List[Dict],
    rwa_protocols: List[Dict],
    defi_tvl: Dict,
) -> Dict[str, Dict[str, Any]]:
    """
    Build sector-level aggregates from live API data.
    """
    sectors = {}
    for sector_id, meta in SECTOR_METADATA.items():
        sectors[sector_id] = {
            "name": meta["name"],
            "risk_level": meta["risk_level"],
            "regulatory_clarity": meta["regulatory_clarity"],
            "total_tvl_usd": 0,
            "total_market_cap_usd": 0,
            "protocol_count": 0,
            "avg_change_24h": 0,
            "avg_change_30d": 0,
            "protocols": [],
            "tokens": [],
        }

    # Aggregate from DeFiLlama protocols
    for protocol in rwa_protocols:
        sector_id = _classify_protocol_to_sector(protocol.get("name", ""))
        if sector_id in sectors:
            sectors[sector_id]["total_tvl_usd"] += protocol.get("tvl_usd", 0)
            sectors[sector_id]["protocol_count"] += 1
            sectors[sector_id]["protocols"].append({
                "name": protocol.get("name"),
                "tvl_usd": protocol.get("tvl_usd", 0),
                "change_1d": protocol.get("change_1d", 0),
                "change_1m": protocol.get("change_1m", 0),
            })

    # Aggregate from CoinGecko RWA tokens
    for token in rwa_tokens:
        # Try to classify token into a sector
        token_name = token.get("name", "").lower()
        sector_id = _classify_protocol_to_sector(token_name)
        if sector_id not in sectors:
            sector_id = "treasury_yield"  # default for RWA tokens

        sectors[sector_id]["total_market_cap_usd"] += token.get("market_cap_usd", 0)
        sectors[sector_id]["tokens"].append({
            "symbol": token.get("symbol"),
            "price_usd": token.get("price_usd", 0),
            "market_cap_usd": token.get("market_cap_usd", 0),
            "change_24h_pct": token.get("change_24h_pct", 0),
            "change_30d_pct": token.get("change_30d_pct", 0),
        })

    # Compute averages
    for sector_id, sector in sectors.items():
        tokens = sector["tokens"]
        protocols = sector["protocols"]
        if tokens:
            sector["avg_change_24h"] = sum(t.get("change_24h_pct", 0) for t in tokens) / len(tokens)
            sector["avg_change_30d"] = sum(t.get("change_30d_pct", 0) for t in tokens) / len(tokens)
        elif protocols:
            sector["avg_change_24h"] = sum(p.get("change_1d", 0) or 0 for p in protocols) / len(protocols)
            sector["avg_change_30d"] = sum(p.get("change_1m", 0) or 0 for p in protocols) / len(protocols)

    return sectors


def _compute_growth_rate(sector: Dict) -> float:
    """Compute effective growth rate from live data."""
    # Use 30d change as growth proxy
    growth = sector.get("avg_change_30d", 0) or 0
    # Boost for high TVL growth
    if sector.get("total_tvl_usd", 0) > 1e9:
        growth += 5  # Large TVL = established sector
    return growth


# ═══════════════════════════════════════════════════════════════════════════════
# Scoring Logic
# ═══════════════════════════════════════════════════════════════════════════════

def _score_sector(
    sector: Dict[str, Any],
    growth_rate: float,
    risk_tolerance: str,
    target_roi: float,
) -> int:
    """Score a sector 0–100 based on live data and risk profile."""
    score = 0

    # Growth rate contribution (0-30 pts)
    if target_roi <= 10:
        score += min(30, int(abs(growth_rate) * 1.5)) if growth_rate > 0 else 5
    elif target_roi <= 20:
        score += min(30, int(abs(growth_rate) * 1.0)) if growth_rate > 0 else 5
    else:
        score += min(30, int(abs(growth_rate) * 0.8)) if growth_rate > 0 else 5

    # TVL contribution (0-20 pts) — bigger TVL = more mature/trusted
    tvl = sector.get("total_tvl_usd", 0)
    if tvl > 5e9:
        score += 20
    elif tvl > 1e9:
        score += 15
    elif tvl > 100e6:
        score += 10
    elif tvl > 0:
        score += 5

    # Regulatory clarity (0-15 pts)
    reg_scores = {"HIGH": 15, "MEDIUM": 9, "LOW": 3}
    score += reg_scores.get(sector.get("regulatory_clarity", "MEDIUM"), 9)

    # Risk alignment (0-20 pts)
    risk_match = {
        "conservative": {"LOW": 20, "MEDIUM": 8, "HIGH": 2},
        "moderate": {"LOW": 15, "MEDIUM": 20, "HIGH": 8},
        "aggressive": {"LOW": 8, "MEDIUM": 15, "HIGH": 20},
    }
    score += risk_match.get(risk_tolerance, {}).get(sector.get("risk_level", "MEDIUM"), 10)

    # Protocol/token count (0-15 pts) — more protocols = more competitive
    count = sector.get("protocol_count", 0) + len(sector.get("tokens", []))
    if count >= 5:
        score += 15
    elif count >= 3:
        score += 10
    elif count >= 1:
        score += 5

    return min(100, max(0, score))


# ═══════════════════════════════════════════════════════════════════════════════
# Main Agent Function
# ═══════════════════════════════════════════════════════════════════════════════

def run_industry_analysis(customer_risk_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run industry analysis using LIVE data from CoinGecko & DeFiLlama.
    """
    try:
        profile = customer_risk_profile or {}
        risk_tolerance = profile.get("risk_tolerance", "moderate")
        target_roi = profile.get("target_roi_pct", 15.0)

        # Fetch live data
        rwa_tokens = fetch_rwa_category_tokens()
        rwa_protocols = fetch_rwa_protocols()
        defi_tvl = fetch_defi_tvl()
        global_market = fetch_global_market_data()

        # Build sector aggregates from live data
        sectors = _build_sector_data_from_live(rwa_tokens, rwa_protocols, defi_tvl)

        # Get relevant sectors for this risk profile
        relevant_sector_ids = RISK_SECTOR_MAP.get(risk_tolerance, RISK_SECTOR_MAP["moderate"])

        # Score each sector
        sector_scores = {}
        scored_sectors = []
        for sector_id in relevant_sector_ids:
            sector = sectors.get(sector_id, {})
            if not sector.get("name"):
                continue

            growth_rate = _compute_growth_rate(sector)
            score = _score_sector(sector, growth_rate, risk_tolerance, target_roi)
            sector_scores[sector_id] = score

            scored_sectors.append({
                "sector_id": sector_id,
                "name": sector["name"],
                "score": score,
                "growth_rate_pct": round(growth_rate, 2),
                "total_tvl_usd": sector["total_tvl_usd"],
                "total_market_cap_usd": sector["total_market_cap_usd"],
                "risk_level": sector["risk_level"],
                "regulatory_clarity": sector["regulatory_clarity"],
                "protocol_count": sector["protocol_count"],
                "token_count": len(sector.get("tokens", [])),
                "avg_change_24h": round(sector["avg_change_24h"], 2),
                "avg_change_30d": round(sector["avg_change_30d"], 2),
                "top_protocols": [p["name"] for p in sector.get("protocols", [])[:5]],
                "top_tokens": [t["symbol"] for t in sector.get("tokens", [])[:5]],
            })

        # Sort by score
        scored_sectors.sort(key=lambda x: x["score"], reverse=True)
        top_sectors = scored_sectors[:4]

        # Growth outlook from live data
        avg_growth = sum(s["growth_rate_pct"] for s in top_sectors) / max(len(top_sectors), 1)
        if avg_growth >= 20:
            growth_outlook = "VERY_POSITIVE"
        elif avg_growth >= 8:
            growth_outlook = "POSITIVE"
        elif avg_growth >= 0:
            growth_outlook = "NEUTRAL"
        else:
            growth_outlook = "CAUTIOUS"

        # Risk alignment
        if risk_tolerance == "conservative" and all(s["risk_level"] == "LOW" for s in top_sectors):
            risk_alignment = "STRONG"
        elif risk_tolerance == "aggressive" and any(s["risk_level"] == "HIGH" for s in top_sectors):
            risk_alignment = "STRONG"
        else:
            risk_alignment = "MODERATE"

        result = {
            "sector_scores": sector_scores,
            "top_sectors": [s["name"] for s in top_sectors],
            "top_sector_ids": [s["sector_id"] for s in top_sectors],
            "recommended_sectors": scored_sectors,
            "growth_outlook": growth_outlook,
            "risk_alignment": risk_alignment,
            "total_sectors_analyzed": len(scored_sectors),
            "rwa_tokens_tracked": len(rwa_tokens),
            "rwa_protocols_tracked": len(rwa_protocols),
            "global_market": global_market,
            "data_source": "LIVE (CoinGecko + DeFiLlama)",
        }

        logger.info(
            "[IndustryAgent] Analyzed %d sectors (live) | Top: %s | Outlook: %s",
            len(scored_sectors),
            ", ".join(s["name"] for s in top_sectors[:3]),
            growth_outlook,
        )
        return result

    except Exception as e:
        logger.error("[IndustryAgent] Error: %s", e, exc_info=True)
        return {
            "error": str(e),
            "sector_scores": {},
            "top_sectors": [],
            "recommended_sectors": [],
            "growth_outlook": "UNKNOWN",
            "risk_alignment": "UNKNOWN",
            "data_source": "ERROR",
        }
