"""
state.py — Shared Agent State Schema
======================================
Defines the TypedDict that flows through the entire agent graph.

Flow: Customer Risk Profiling → Macro Analysis → Match Asset → ...
"""

from typing import TypedDict, Optional, List, Dict, Any


class AgentState(TypedDict, total=False):
    # ── User Input ──────────────────────────────────────────────────────
    user_input: str
    session_id: str

    # ── Customer Risk Profiling Agent Output ────────────────────────────
    customer_risk_profile: Optional[Dict[str, Any]]
    # Expected shape:
    # {
    #   "risk_tolerance": "conservative" | "moderate" | "aggressive",
    #   "investment_horizon": "short" | "medium" | "long",
    #   "target_roi_pct": float,
    #   "budget_usd": float,
    #   "preferred_asset_types": List[str],
    #   "jurisdiction": str,
    #   "kyc_status": str,
    # }

    # ── Macro Analysis Agent Output ─────────────────────────────────────
    macro_analysis_report: Optional[Dict[str, Any]]
    # Expected shape:
    # {
    #   "industry_analysis": {...},
    #   "financial_analysis": {...},
    #   "cash_flow_analysis": {...},
    #   "geopolitical_analysis": {...},
    #   "market_analysis": {...},
    #   "overall_macro_score": int,
    #   "recommended_asset_types": List[str],
    # }

    # ── Individual Sub-Agent Outputs (for granular access) ──────────────
    industry_analysis: Optional[Dict[str, Any]]
    financial_analysis: Optional[Dict[str, Any]]
    cash_flow_analysis: Optional[Dict[str, Any]]
    geopolitical_analysis: Optional[Dict[str, Any]]
    market_analysis: Optional[Dict[str, Any]]

    # ── Match Asset Agent Output (future) ───────────────────────────────
    matched_assets: Optional[List[Dict[str, Any]]]

    # ── Final Output ────────────────────────────────────────────────────
    result: str
    error: Optional[str]
