"""
agents/ - Multi-Agent Pipeline Modules
=======================================
Each module exports a single node function for the LangGraph pipeline.
"""

from agents.customer_profiling import customer_profiling_agent
from agents.macro_analysis import macro_analysis_agent
from agents.industry_analysis import industry_analysis_agent
from agents.financial_analysis import financial_analysis_agent
from agents.cashflow_analysis import cashflow_analysis_agent
from agents.geopolitical_analysis import geopolitical_analysis_agent
from agents.market_analysis import market_analysis_agent
from agents.match_asset import match_asset_agent
from agents.asset_class_analysis import asset_class_analysis_agent
from agents.asset_analysis import asset_analysis_agent

__all__ = [
    "customer_profiling_agent",
    "macro_analysis_agent",
    "industry_analysis_agent",
    "financial_analysis_agent",
    "cashflow_analysis_agent",
    "geopolitical_analysis_agent",
    "market_analysis_agent",
    "match_asset_agent",
    "asset_class_analysis_agent",
    "asset_analysis_agent",
]
