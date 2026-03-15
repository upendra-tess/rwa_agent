# ============================================================
# main.py — CLI Entry Point for the AI Wallet Agent
# ============================================================
# Run this file to start the interactive agent:
#
#   cd ai_wallet_agent
#   pip install -r requirements.txt
#   python main.py
#
# Then type natural-language commands like:
#   "check my wallet balance"
#   "check agent wallet balance"
#   "transfer 0.01 eth to agent wallet"
#   "quit" or "exit" to stop
# ============================================================

from agent_graph import build_graph


def main():
    """Launch the interactive CLI loop."""

    # ---- Compile the LangGraph state machine ----
    print("\n==============================================")
    print("   AI Wallet Agent  (Sepolia Testnet)")
    print("==============================================")
    print("Commands you can try:")
    print("  • check my wallet balance")
    print("  • check agent wallet balance")
    print("  • transfer 0.01 eth to agent wallet")
    print("  • create a new wallet")
    print('  • Type "quit" or "exit" to stop\n')

    agent = build_graph()

    # ---- Main loop — read input, run graph, print result ----
    while True:
        # Get user input
        user_input = input("You: ").strip()

        # Exit conditions
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        # Skip empty input
        if not user_input:
            continue

        # Build the initial state and invoke the graph
        initial_state = {
            "user_input": user_input,
            "intent": "",
            "amount": "",
            "result": "",
        }

        # Run the LangGraph agent
        final_state = agent.invoke(initial_state)

        # Print the result
        print(f"Agent: {final_state.get('result', 'No response.')}\n")


# ---- Standard Python entry point ----
if __name__ == "__main__":
    main()
