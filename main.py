"""
main.py - CLI Entry Point for the RWA Multi-Agent System
=========================================================
Runs the full multi-agent pipeline:
  Customer Profiling -> Macro Analysis -> [5 Parallel Agents]
  -> Match Asset -> Asset Class Analysis -> Asset Analysis -> Output

Usage:
  cd rwa-multi-agent
  pip install -r requirements.txt
  python main.py

Then describe your investment goals in natural language, e.g.:
  "I have $50,000 to invest in RWA tokens. I'm based in the US,
   looking for 12% annual returns over 2 years, moderate risk,
   with monthly redemption access."
"""

import logging
import sys

from agent_graph import build_graph
from agents.conversational_profiler import ConversationalProfiler

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

    # Opening question
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


def main():
    """Launch the interactive multi-agent CLI."""
    print("\n" + "=" * 60)
    print("   RWA Multi-Agent Asset Analyzer")
    print("=" * 60)
    print()
    print('Type "quit" or "exit" at any time to stop.')
    print()

    agent = build_graph()

    while True:
        # Step 1: Conversational profiling
        profile = run_conversation()
        profile["_from_conversation"] = True

        logger.info(
            "Profile collected: budget=$%.0f region=%s risk=%s horizon=%dmo return=%.1f%%",
            profile["budget"], profile["region"], profile["risk_tolerance"],
            profile["time_horizon_months"], profile["expected_return_pct"],
        )

        print("\nRunning market analysis across 10 specialized agents...")
        print("  Watch the log timestamps for progress.\n")

        # Step 2: Run the pipeline with the pre-built profile
        initial_state = {
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

        try:
            final_state = agent.invoke(initial_state)
            result = final_state.get("result", "No result generated.")
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
