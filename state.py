"""
state.py - Multi-Agent Pipeline State
======================================
Shared state flowing through the LangGraph multi-agent pipeline.

Pipeline:
  Customer Profiling -> Macro Analysis -> [5 Parallel Agents] -> Match Asset
  -> Asset Class Analysis -> Asset Analysis -> Final Output
"""

from typing import TypedDict, Optional, Annotated
import operator


def merge_dict(left: dict, right: dict) -> dict:
    """Reducer that merges dicts (used for parallel fan-in)."""
    merged = left.copy() if left else {}
    if right:
        merged.update(right)
    return merged


class MultiAgentState(TypedDict):
    # --- User input ---
    user_input: str

    # --- RWA Universe (fetched live from DefiLlama RWA category) ---
    rwa_universe: list
    # List of dicts from DefiLlama: name, slug, tvl, chain, category,
    # gecko_id, symbol, description, chains, change_1d, change_7d, mcap, etc.
    # This is the SINGLE SOURCE OF TRUTH for all assets in the pipeline.

    # --- Customer Profile (from Customer Profiling Agent) ---
    customer_profile: dict
    # Expected keys:
    #   budget: float (USD)
    #   region: str (e.g. "US", "EU", "APAC", "LATAM", "MENA", "GLOBAL")
    #   time_horizon_months: int
    #   expected_return_pct: float
    #   redemption_window: str (e.g. "daily", "weekly", "monthly", "quarterly", "locked")
    #   risk_tolerance: str (e.g. "conservative", "moderate", "aggressive")

    # --- Macro Analysis (from Macro Analysis Agent) ---
    macro_context: dict
    # Expected keys:
    #   rate_environment, macro_regime, yield_curve, rwa_attractiveness,
    #   key_rates (dict of yield values), market_indicators (dxy, vix, etc.)

    # --- Parallel Analysis Results (fan-in with merge) ---
    industry_analysis: Annotated[dict, merge_dict]
    financial_analysis: Annotated[dict, merge_dict]
    cashflow_analysis: Annotated[dict, merge_dict]
    geopolitical_analysis: Annotated[dict, merge_dict]
    market_analysis: Annotated[dict, merge_dict]

    # --- Match Asset Agent ---
    matched_assets: list
    # List of asset dicts ranked by fit to customer profile

    # --- Asset Class Analysis Agent ---
    asset_class_analysis: dict
    # Expected keys:
    #   correlations: dict (pairwise correlation matrix)
    #   anti_correlations: list (pairs with negative correlation)
    #   r_squared: dict (R^2 values per asset pair)
    #   diversification_score: float
    #   recommended_mix: list

    # --- Asset Analysis Agent (final filter) ---
    filtered_assets: list
    # Final filtered list after legal, regulatory, yield, redemption checks

    # --- Final output ---
    result: str
