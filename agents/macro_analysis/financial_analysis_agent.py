"""
financial_analysis_agent.py — Financial Analysis Sub-Agent
===========================================================
Analyzes macroeconomic financial indicators using LIVE data:
interest rates, inflation, GDP, credit conditions.

Data Sources:
  - US Treasury API         → Treasury yield rates
  - World Bank API          → GDP growth, inflation, interest rates
  - CoinGecko               → Stablecoin peg data (DXY proxy)
  - DeFiLlama               → DeFi yield environment

Input:  customer_risk_profile dict
Output: financial_analysis dict with macro financial scores
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

from .data_pipeline import (
    fetch_treasury_yields,
    fetch_world_bank,
    fetch_fred_macro,
    fetch_nfci,
    fetch_imf_indicators,
    fetch_ecb_rates,
    fetch_defi_stablecoins,
    fetch_yield_pools,
    fetch_stablecoin_peg,
    fetch_token_prices,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Analysis Logic (driven by live data)
# ═══════════════════════════════════════════════════════════════════════════════

def _classify_rate_environment(treasury_yields: Dict, macro: Dict) -> Dict[str, Any]:
    """Classify interest rate environment from live Treasury data."""
    # Try to get a representative rate
    rate = 0
    rate_source = "unknown"

    # From Treasury API
    if treasury_yields:
        if "10y" in treasury_yields:
            rate = float(treasury_yields["10y"])
            rate_source = "treasury_10y"
        elif "treasury_notes_avg" in treasury_yields:
            rate = float(treasury_yields["treasury_notes_avg"])
            rate_source = "treasury_notes_avg"
        elif "treasury_bills_avg" in treasury_yields:
            rate = float(treasury_yields["treasury_bills_avg"])
            rate_source = "treasury_bills_avg"

    # From World Bank as fallback
    if rate == 0 and macro.get("interest_rate"):
        rate = float(macro["interest_rate"].get("value", 0))
        rate_source = "world_bank_real_rate"

    if rate >= 4.5:
        env = "HIGH"
    elif rate >= 2.0:
        env = "MODERATE"
    else:
        env = "LOW"

    return {
        "environment": env,
        "rate_value": rate,
        "source": rate_source,
    }


def _assess_inflation(macro: Dict) -> Dict[str, Any]:
    """Assess inflation impact from World Bank data."""
    inflation_data = macro.get("inflation_cpi", {})
    inflation_rate = float(inflation_data.get("value", 0)) if inflation_data else 0
    year = inflation_data.get("year", "unknown") if inflation_data else "unknown"

    if inflation_rate > 5.0:
        severity = "HIGH"
        recommendation = "Favor inflation-hedged assets: commodities, real estate, TIPS-linked tokens"
    elif inflation_rate > 3.0:
        severity = "MODERATE"
        recommendation = "Balanced approach: mix of fixed-income and real assets"
    elif inflation_rate > 0:
        severity = "LOW"
        recommendation = "Fixed-income RWAs are attractive at current inflation levels"
    else:
        severity = "UNKNOWN"
        recommendation = "Inflation data unavailable — use conservative assumptions"

    return {
        "severity": severity,
        "current_rate": inflation_rate,
        "data_year": year,
        "recommendation": recommendation,
    }


def _assess_gdp(macro: Dict) -> Dict[str, Any]:
    """Assess GDP growth from World Bank data."""
    gdp_data = macro.get("gdp_growth", {})
    gdp_rate = float(gdp_data.get("value", 0)) if gdp_data else 0
    year = gdp_data.get("year", "unknown") if gdp_data else "unknown"

    if gdp_rate > 3.0:
        outlook = "STRONG"
    elif gdp_rate > 1.5:
        outlook = "MODERATE"
    elif gdp_rate > 0:
        outlook = "WEAK"
    else:
        outlook = "CONTRACTION"

    return {
        "growth_rate": gdp_rate,
        "outlook": outlook,
        "data_year": year,
    }


def _assess_yield_environment(yield_pools: list) -> Dict[str, Any]:
    """Assess DeFi yield environment from DeFiLlama data."""
    if not yield_pools:
        return {"avg_apy": 0, "stablecoin_avg_apy": 0, "pool_count": 0}

    all_apys = [p["apy"] for p in yield_pools if p.get("apy", 0) > 0]
    stable_pools = [p for p in yield_pools if p.get("stablecoin")]
    stable_apys = [p["apy"] for p in stable_pools if p.get("apy", 0) > 0]

    return {
        "avg_apy": round(sum(all_apys) / len(all_apys), 2) if all_apys else 0,
        "median_apy": round(sorted(all_apys)[len(all_apys) // 2], 2) if all_apys else 0,
        "stablecoin_avg_apy": round(sum(stable_apys) / len(stable_apys), 2) if stable_apys else 0,
        "pool_count": len(yield_pools),
        "stablecoin_pool_count": len(stable_pools),
        "top_yield_pools": [
            {"project": p["project"], "symbol": p["symbol"], "apy": p["apy"], "tvl": p["tvl_usd"]}
            for p in yield_pools[:10]
        ],
    }


def _recommend_duration(rate_env: str, risk_tolerance: str) -> str:
    """Recommend investment duration based on rate environment."""
    matrix = {
        ("HIGH", "conservative"): "SHORT",
        ("HIGH", "moderate"): "SHORT_TO_MEDIUM",
        ("HIGH", "aggressive"): "MEDIUM",
        ("MODERATE", "conservative"): "MEDIUM",
        ("MODERATE", "moderate"): "MEDIUM_TO_LONG",
        ("MODERATE", "aggressive"): "LONG",
        ("LOW", "conservative"): "MEDIUM",
        ("LOW", "moderate"): "LONG",
        ("LOW", "aggressive"): "LONG",
    }
    return matrix.get((rate_env, risk_tolerance), "MEDIUM")


def _compute_financial_score(
    rate_env: str,
    inflation_severity: str,
    gdp_outlook: str,
    stablecoin_peg: bool,
    risk_tolerance: str,
) -> int:
    """Compute financial environment score (0-100) from live data."""
    score = 50

    # Rate environment
    if rate_env == "HIGH":
        score += 10 if risk_tolerance == "conservative" else -5
    elif rate_env == "LOW":
        score -= 5 if risk_tolerance == "conservative" else 10

    # Inflation
    inflation_adj = {"LOW": 15, "MODERATE": 5, "HIGH": -10, "UNKNOWN": 0}
    score += inflation_adj.get(inflation_severity, 0)

    # GDP growth
    gdp_adj = {"STRONG": 10, "MODERATE": 5, "WEAK": -5, "CONTRACTION": -15}
    score += gdp_adj.get(gdp_outlook, 0)

    # Stablecoin peg health (market stability proxy)
    if stablecoin_peg:
        score += 5
    else:
        score -= 10

    return max(0, min(100, score))


# ═══════════════════════════════════════════════════════════════════════════════
# Main Agent Function
# ═══════════════════════════════════════════════════════════════════════════════

def run_financial_analysis(customer_risk_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Run macroeconomic financial analysis using LIVE data.
    """
    try:
        profile = customer_risk_profile or {}
        risk_tolerance = profile.get("risk_tolerance", "moderate")
        target_roi = profile.get("target_roi_pct", 15.0)

        # Fetch live data
        treasury_yields = fetch_treasury_yields()
        world_bank = fetch_world_bank()
        fred = fetch_fred_macro()
        nfci = fetch_nfci()
        imf = fetch_imf_indicators()
        ecb = fetch_ecb_rates()
        yield_pools = fetch_yield_pools()
        stablecoin_peg_data = fetch_stablecoin_peg()

        # Merge macro indicators: prefer FRED > World Bank > IMF
        macro_indicators = {}
        # GDP
        if fred.get("us_gdp_growth"):
            macro_indicators["gdp_growth"] = {"value": fred["us_gdp_growth"]["value"], "year": fred["us_gdp_growth"]["date"]}
        elif world_bank.get("gdp_growth"):
            macro_indicators["gdp_growth"] = world_bank["gdp_growth"]
        elif imf.get("gdp_growth_pct"):
            macro_indicators["gdp_growth"] = {"value": imf["gdp_growth_pct"]["value"], "year": imf["gdp_growth_pct"]["year"]}

        # Inflation
        if fred.get("inflation_cpi_yoy"):
            macro_indicators["inflation_cpi"] = {"value": fred["inflation_cpi_yoy"]["value"], "year": fred["inflation_cpi_yoy"]["date"]}
        elif world_bank.get("inflation_cpi"):
            macro_indicators["inflation_cpi"] = world_bank["inflation_cpi"]
        elif imf.get("inflation_pct"):
            macro_indicators["inflation_cpi"] = {"value": imf["inflation_pct"]["value"], "year": imf["inflation_pct"]["year"]}

        # Interest rate
        if fred.get("fed_funds_rate"):
            macro_indicators["interest_rate"] = {"value": fred["fed_funds_rate"]["value"], "year": fred["fed_funds_rate"]["date"]}
        elif world_bank.get("interest_rate_real"):
            macro_indicators["interest_rate"] = world_bank["interest_rate_real"]

        # NFCI (financial conditions)
        if nfci:
            macro_indicators["nfci"] = nfci

        # ECB
        if ecb:
            macro_indicators["ecb"] = ecb

        # Analyze
        rate_info = _classify_rate_environment(treasury_yields, macro_indicators)
        rate_env = rate_info["environment"]
        inflation_impact = _assess_inflation(macro_indicators)
        gdp_assessment = _assess_gdp(macro_indicators)
        yield_env = _assess_yield_environment(yield_pools)
        recommended_duration = _recommend_duration(rate_env, risk_tolerance)

        # Stablecoin peg check
        stablecoin_data = stablecoin_peg_data
        peg_stable = stablecoin_data.get("peg_stable", True)

        # Compute score
        financial_score = _compute_financial_score(
            rate_env, inflation_impact["severity"],
            gdp_assessment["outlook"], peg_stable, risk_tolerance,
        )

        # Investment implications from live data
        implications = []
        if rate_env == "HIGH":
            implications.append(
                f"High rate environment (Treasury ~{rate_info['rate_value']:.2f}%) — "
                f"treasury-backed RWAs offer competitive risk-free yields"
            )
        if inflation_impact["severity"] != "LOW" and inflation_impact["current_rate"] > 0:
            implications.append(
                f"Inflation at {inflation_impact['current_rate']:.1f}% ({inflation_impact['data_year']}) — "
                f"{inflation_impact['recommendation']}"
            )
        if yield_env.get("stablecoin_avg_apy", 0) > 0:
            implications.append(
                f"DeFi stablecoin yields averaging {yield_env['stablecoin_avg_apy']:.1f}% APY "
                f"across {yield_env['stablecoin_pool_count']} pools"
            )
        if target_roi > rate_info.get("rate_value", 0) and rate_info["rate_value"] > 0:
            spread = target_roi - rate_info["rate_value"]
            implications.append(
                f"Target ROI of {target_roi}% exceeds risk-free rate by {spread:.1f}pp — "
                f"requires allocation to growth/yield assets"
            )
        if gdp_assessment["growth_rate"] > 0:
            implications.append(
                f"GDP growth at {gdp_assessment['growth_rate']:.1f}% ({gdp_assessment['outlook']}) — "
                f"{'supports' if gdp_assessment['outlook'] in ('STRONG', 'MODERATE') else 'caution for'} "
                f"real asset investments"
            )

        result = {
            "interest_rate_environment": rate_env,
            "rate_value": rate_info["rate_value"],
            "rate_source": rate_info["source"],
            "treasury_yields": treasury_yields,
            "inflation_impact": inflation_impact,
            "gdp_assessment": gdp_assessment,
            "yield_environment": yield_env,
            "recommended_duration": recommended_duration,
            "financial_environment_score": financial_score,
            "stablecoin_peg": stablecoin_data,
            "eth_gas": macro_indicators.get("eth_gas", {}),
            "investment_implications": implications,
            "analysis_timestamp": datetime.utcnow().isoformat(),
            "data_source": "LIVE (Treasury.gov + WorldBank + DeFiLlama)",
        }

        logger.info(
            "[FinancialAgent] Rate=%s (%.2f%%) | Inflation=%s | GDP=%s | Score=%d",
            rate_env, rate_info["rate_value"],
            inflation_impact["severity"], gdp_assessment["outlook"],
            financial_score,
        )
        return result

    except Exception as e:
        logger.error("[FinancialAgent] Error: %s", e, exc_info=True)
        return {
            "error": str(e),
            "interest_rate_environment": "UNKNOWN",
            "financial_environment_score": 0,
            "investment_implications": [],
            "data_source": "ERROR",
        }
