"""
main.py — CLI Entry Point for the RWA Agent
=============================================
Run: python main.py

Interactive CLI to test the full agent pipeline:
  Customer Risk Profiling → Macro Analysis → [future stages]
"""

from agent_graph import build_graph


def main():
    """Launch the interactive CLI loop."""

    print("\n==============================================")
    print("   RWA Investment Agent")
    print("==============================================")
    print("Describe your investment goals and I'll analyze")
    print("the macro environment for RWA opportunities.\n")
    print("Examples:")
    print("  • I want 15% ROI with $10k budget, moderate risk")
    print("  • Conservative investor, $50k, stable returns")
    print("  • Aggressive growth, maximize returns, $5000")
    print('  • Type "quit" or "exit" to stop\n')

    agent = build_graph()

    while True:
        user_input = input("You: ").strip()

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        if not user_input:
            continue

        initial_state = {
            "user_input": user_input,
            "session_id": "",
            "result": "",
        }

        try:
            final_state = agent.invoke(initial_state)
            print(f"\nAgent:\n{final_state.get('result', 'No response.')}\n")
        except Exception as e:
            print(f"\nError: {e}\n")


if __name__ == "__main__":
    main()
