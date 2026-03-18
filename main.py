"""
main.py - CLI Entry Point for the RWA Multi-Agent System
=========================================================
Now with Agent Memory:
  - Cache is warmed on startup (runs market agents once)
  - User requests use the FAST path (injects cached market data)
  - Cache auto-refreshes every 30 min in background

Usage:
  cd rwa_agent
  pip install -r requirements.txt
  python main.py

Then describe your investment goals in natural language, e.g.:
  "I have $50,000 to invest in RWA tokens. I'm based in the US,
   looking for 12% annual returns over 2 years, moderate risk,
   with monthly redemption access."
"""

import logging
import sys

from agent_cache import cache
from scheduler import start_scheduler, refresh_cache_now
from agents.conversational_profiler import ConversationalProfiler
from agents import (
    match_asset_agent,
    asset_class_analysis_agent,
    asset_analysis_agent,
    # Full pipeline agents (used as fallback when cache is cold)
    macro_analysis_agent,
    industry_analysis_agent,
    financial_analysis_agent,
    cashflow_analysis_agent,
    geopolitical_analysis_agent,
    market_analysis_agent,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_conversation() -> dict:
    """Run the conversational profiler and return the completed profile."""
    profiler = ConversationalProfiler()

    opening = profiler.start()
    print(f"\nAnalyst: {opening}\n")

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            sys.exit(0)

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            sys.exit(0)

        if not user_input:
            continue

        message, complete = profiler.respond(user_input)
        print(f"\nAnalyst: {message}\n")

        if complete:
            break

    return profiler.get_profile()


def _build_initial_state(profile: dict) -> dict:
    """Build LangGraph initial state, injecting cached market data if available."""
    base = {
        "user_input": "",
        "rwa_universe": [],
        "customer_profile": profile,
        "macro_context": {},
        "industry_analysis": {},
        "financial_analysis": {},
        "cashflow_analysis": {},
        "geopolitical_analysis": {},
        "market_analysis": {},
        "matched_assets": [],
        "asset_class_analysis": {},
        "filtered_assets": [],
        "result": "",
    }

    # Inject all fresh cached values
    cached = cache.get_all_cached_state()
    if cached:
        base.update(cached)
        logger.info("[main] Injected %d cached keys: %s", len(cached), list(cached.keys()))

    return base


def run_pipeline(profile: dict) -> str:
    """
    Run the analysis pipeline for a customer profile.
    Uses cached market data when available (FAST PATH).
    Falls back to full live pipeline if cache is cold.
    """
    state = _build_initial_state(profile)
    use_cache = cache.is_warm()

    if use_cache:
        print("\n✅ Using pre-computed market intelligence (cached) — personalized analysis only...\n")
        logger.info("[main] FAST PATH: cache hit — running 3 user-specific agents")
    else:
        print("\n⏳ Cache is cold — running full market analysis (30-60s)...\n")
        logger.info("[main] FULL PATH: cache miss — running all 10 agents")

        # Run macro first
        print("  [1/7] Macro Analysis...")
        state = macro_analysis_agent(state)

        # 5 parallel agents (run sequentially in CLI mode for simplicity)
        for i, (name, fn) in enumerate([
            ("Industry Analysis",    industry_analysis_agent),
            ("Financial Analysis",   financial_analysis_agent),
            ("Cash Flow",            cashflow_analysis_agent),
            ("Geopolitical",         geopolitical_analysis_agent),
            ("Market Analysis",      market_analysis_agent),
        ], start=2):
            print(f"  [{i}/7] {name}...")
            result = fn(state)
            state.update(result)

    # User-specific agents (always run live)
    print("  Matching assets to your profile...")
    state = match_asset_agent(state)

    print("  Analyzing asset classes...")
    state = asset_class_analysis_agent(state)

    print("  Finalizing recommendations...")
    state = asset_analysis_agent(state)

    return state.get("result", "No result generated.")


def main():
    """Launch the interactive multi-agent CLI."""
    print("\n" + "=" * 60)
    print("   RWA Multi-Agent Asset Analyzer")
    print("=" * 60)
    print()

    # Start background scheduler (warms cache immediately, then refreshes every 30 min)
    print("⚙️  Starting background cache scheduler...")
    start_scheduler(interval_minutes=30, warmup=True)
    print(f"✅ Cache warm: {cache.is_warm()}\n")

    print('Type "quit" or "exit" at any time to stop.')
    print()

    while True:
        # Step 1: Conversational profiling
        profile = run_conversation()
        profile["_from_conversation"] = True

        logger.info(
            "Profile: budget=$%.0f region=%s risk=%s horizon=%dmo return=%.1f%%",
            profile["budget"], profile["region"], profile["risk_tolerance"],
            profile["time_horizon_months"], profile["expected_return_pct"],
        )

        # Step 2: Run the pipeline (fast or full)
        try:
            result = run_pipeline(profile)
            print(f"\n{result}\n")
        except Exception as e:
            logger.error("Pipeline error: %s", e, exc_info=True)
            print(f"\nError during analysis: {e}")
            print("Please try again.\n")

        # Ask if user wants another analysis
        print("-" * 60)
        try:
            again = input("Run another analysis? (yes/no): ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        if again not in ("yes", "y"):
            print("Goodbye!")
            break
        print()


if __name__ == "__main__":
    main()
