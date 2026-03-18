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

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    """Launch the interactive multi-agent CLI."""
    print("\n" + "=" * 60)
    print("   RWA Multi-Agent Investment Advisor")
    print("=" * 60)
    print()
    print("Describe your investment goals. I'll analyze the market")
    print("across 10 specialized agents and recommend a portfolio.")
    print()
    print("Example prompts:")
    print("  - I have $25,000, US-based, want 15% returns in 1 year")
    print("  - Conservative investor, $100k budget, EU region,")
    print("    need monthly liquidity, targeting 8% yield")
    print("  - Aggressive crypto-native, $5k, 2-year horizon,")
    print("    willing to lock funds for higher yield")
    print()
    print('Type "quit" or "exit" to stop.')
    print()

    agent = build_graph()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        if not user_input:
            continue

        print("\nRunning multi-agent analysis pipeline...")
        print("  [1/4] Customer profiling + fetching RWA universe...")

        initial_state = {
            "user_input": user_input,
            "rwa_universe": [],
            "customer_profile": {},
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
            print(f"\nAgent:\n{result}\n")
        except Exception as e:
            logger.error("Pipeline error: %s", e, exc_info=True)
            print(f"\nError during analysis: {e}")
            print("Please try again with a different query.\n")


if __name__ == "__main__":
    main()
