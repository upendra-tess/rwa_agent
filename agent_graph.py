"""
agent_graph.py - LangGraph Multi-Agent Pipeline
=================================================
TWO graph modes:

1. FULL GRAPH (build_graph) — used by scheduler for cache refresh:
   Customer Profiling -> Macro Analysis -> [5 Parallel Agents] -> Match Asset
   -> Asset Class Analysis -> Asset Analysis -> Final Output

2. FAST GRAPH (build_fast_graph) — used for user requests (reads from cache):
   Customer Profiling -> Match Asset -> Asset Class Analysis -> Asset Analysis -> END
   (macro + 5 parallel agents are pre-computed and injected from cache)

The 5 parallel agents (fan-out / fan-in):
  - Industry Analysis Agent
  - Financial Analysis Agent
  - Cash Flow Agent
  - Geopolitical Analysis Agent
  - Market Analysis Agent
"""

import logging
from langgraph.graph import StateGraph, END

from state import MultiAgentState
from agents import (
    customer_profiling_agent,
    macro_analysis_agent,
    industry_analysis_agent,
    financial_analysis_agent,
    cashflow_analysis_agent,
    geopolitical_analysis_agent,
    market_analysis_agent,
    match_asset_agent,
    asset_class_analysis_agent,
    asset_analysis_agent,
)

logger = logging.getLogger(__name__)


def build_graph():
    """
    Build and compile the FULL multi-agent LangGraph pipeline.
    Used by the scheduler for cache refresh — runs ALL agents including
    live API calls and LLM inference.

    Graph topology:
        customer_profiling
              |
        macro_analysis
         /  |  |  |  \\
        IA  FA  CF GEO MKT    (parallel fan-out)
         \\  |  |  |  /
         match_asset            (fan-in: waits for all 5)
              |
        asset_class_analysis
              |
        asset_analysis
              |
             END
    """
    graph = StateGraph(MultiAgentState)

    # --- Register all nodes ---
    graph.add_node("customer_profiling", customer_profiling_agent)
    graph.add_node("macro_analysis", macro_analysis_agent)

    # Parallel analysis agents
    graph.add_node("industry_analysis", industry_analysis_agent)
    graph.add_node("financial_analysis", financial_analysis_agent)
    graph.add_node("cashflow_analysis", cashflow_analysis_agent)
    graph.add_node("geopolitical_analysis", geopolitical_analysis_agent)
    graph.add_node("market_analysis", market_analysis_agent)

    # Downstream sequential agents
    graph.add_node("match_asset", match_asset_agent)
    graph.add_node("asset_class_analysis", asset_class_analysis_agent)
    graph.add_node("asset_analysis", asset_analysis_agent)

    # --- Entry point ---
    graph.set_entry_point("customer_profiling")

    # --- Sequential edges: profiling -> macro ---
    graph.add_edge("customer_profiling", "macro_analysis")

    # --- Fan-out: macro -> 5 parallel agents ---
    graph.add_edge("macro_analysis", "industry_analysis")
    graph.add_edge("macro_analysis", "financial_analysis")
    graph.add_edge("macro_analysis", "cashflow_analysis")
    graph.add_edge("macro_analysis", "geopolitical_analysis")
    graph.add_edge("macro_analysis", "market_analysis")

    # --- Fan-in: 5 agents -> match_asset ---
    graph.add_edge("industry_analysis", "match_asset")
    graph.add_edge("financial_analysis", "match_asset")
    graph.add_edge("cashflow_analysis", "match_asset")
    graph.add_edge("geopolitical_analysis", "match_asset")
    graph.add_edge("market_analysis", "match_asset")

    # --- Sequential: match -> asset_class -> asset_analysis -> END ---
    graph.add_edge("match_asset", "asset_class_analysis")
    graph.add_edge("asset_class_analysis", "asset_analysis")
    graph.add_edge("asset_analysis", END)

    return graph.compile()


def build_fast_graph():
    """
    Build and compile the FAST user-facing graph.
    Skips macro + 5 parallel agents (those come from cache).

    Graph topology:
        customer_profiling
              |
        match_asset          (cache provides macro + 5 analysis results)
              |
        asset_class_analysis
              |
        asset_analysis
              |
             END

    The initial_state must be pre-populated with cached values for:
      - rwa_universe
      - macro_context
      - industry_analysis
      - financial_analysis
      - cashflow_analysis
      - geopolitical_analysis
      - market_analysis
    """
    graph = StateGraph(MultiAgentState)

    # Only the user-specific agents
    graph.add_node("customer_profiling", customer_profiling_agent)
    graph.add_node("match_asset", match_asset_agent)
    graph.add_node("asset_class_analysis", asset_class_analysis_agent)
    graph.add_node("asset_analysis", asset_analysis_agent)

    # Linear pipeline
    graph.set_entry_point("customer_profiling")
    graph.add_edge("customer_profiling", "match_asset")
    graph.add_edge("match_asset", "asset_class_analysis")
    graph.add_edge("asset_class_analysis", "asset_analysis")
    graph.add_edge("asset_analysis", END)

    return graph.compile()
