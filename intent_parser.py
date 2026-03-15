"""
intent_parser.py — Claude-powered intent detection
===================================================
Parses user messages into structured intents for routing.

Supported intents:
  WALLET OPS:
    check_user_balance    → show my ETH balance
    check_agent_balance   → show agent wallet balance
    transfer_to_agent     → send ETH to agent
    create_wallet         → generate new wallet

  TRADING INTELLIGENCE:
    analyze_market        → I want 20% ROI / analyze market / best tokens
    suggest_trades        → suggest trades / how should I trade / execute
    token_info            → tell me about ONDO / analyze ETH / what is LINK
    market_status         → market status / how is the market / fear greed
    verify_rwa            → verify ONDO / is maple legit / trust score

  FALLBACK:
    unknown               → anything not matched above
"""

import json
import logging
from state import AgentState
from bedrock_client import BedrockClient

logger = logging.getLogger(__name__)
bedrock = BedrockClient()

INTENT_PROMPT = """
You are an intent-detection assistant for an AI crypto wallet + trading agent.

Given the user's message, determine which action they want.

INTENTS:
=== WALLET OPERATIONS ===
1. "check_user_balance"   — user wants to see their own wallet balance
2. "check_agent_balance"  — user wants to see the agent wallet balance
3. "transfer_to_agent"    — user wants to send ETH to the agent wallet
4. "create_wallet"        — user wants to create a new Ethereum wallet

=== TRADING INTELLIGENCE ===
5. "analyze_market"       — user wants market analysis, token ranking, ROI projections, best tokens to buy
                            EXAMPLES: "I want 20% ROI", "analyze the market", "which tokens should I buy",
                            "best tokens for 2026", "what should I invest in", "give me top picks"

6. "suggest_trades"       — user wants a concrete trade execution plan with gas/slippage details
                            EXAMPLES: "suggest trades", "how should I trade", "give me a trade plan",
                            "execute my strategy", "what trades to make", "buy recommendations"

7. "token_info"           — user wants deep analysis of a specific token
                            EXAMPLES: "tell me about ONDO", "analyze ETH", "what is LINK doing",
                            "AAVE analysis", "explain Pendle", "how is UNI performing"

8. "market_status"        — user wants current market overview (fear/greed, top movers)
                            EXAMPLES: "market status", "how is the market", "what's happening in crypto",
                            "fear and greed index", "top gainers today", "market overview"

9. "verify_rwa"           — user wants to verify a Real World Asset (RWA) token's legitimacy
                            EXAMPLES: "verify ONDO", "is maple legit", "trust score for goldfinch",
                            "check if centrifuge is safe", "RWA verification", "is clearpool real"

=== FALLBACK ===
10. "unknown"             — anything not matching above

Return ONLY valid JSON (no markdown, no explanation):
{{
  "intent": "<one of the 10 intents above>",
  "amount": "<USD or ETH amount as string if mentioned, else empty string>",
  "token_id": "<CoinGecko token ID if a specific token is mentioned, else empty string>",
  "roi_target": "<ROI percentage as string if mentioned, e.g. '20', else empty string>"
}}

IMPORTANT RULES:
- If user mentions ANY token by name or symbol, set token_id (e.g. "ONDO" → "ondo-finance", "ETH" → "ethereum")
- If user mentions a % target return, set roi_target (e.g. "20% return" → "20")
- If user mentions a dollar amount, set amount (e.g. "$500" → "500")
- Prefer "analyze_market" for general portfolio/ROI questions
- Prefer "token_info" when a SPECIFIC token is named and they want analysis
- Prefer "verify_rwa" when user asks about legitimacy/safety of a token

User message: {user_input}
"""

# Token symbol → CoinGecko ID quick map (used as fallback)
TOKEN_MAP = {
    "btc": "bitcoin", "eth": "ethereum", "link": "chainlink",
    "aave": "aave", "uni": "uniswap", "mkr": "maker",
    "crv": "curve-dao-token", "ldo": "lido-dao",
    "arb": "arbitrum", "op": "optimism",
    "ondo": "ondo-finance", "cfg": "centrifuge",
    "mpl": "maple", "gfi": "goldfinch", "cpool": "clearpool",
    "pendle": "pendle", "gmx": "gmx", "gns": "gains-network",
}


def parse_intent(state: AgentState) -> dict:
    prompt = INTENT_PROMPT.format(user_input=state["user_input"])
    raw_response = bedrock.send_message(prompt)

    text = raw_response.strip()
    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("[intent_parser] Failed to parse JSON: %s", text[:200])
        parsed = {}

    intent    = parsed.get("intent", "unknown")
    amount    = parsed.get("amount", "") or ""
    token_id  = parsed.get("token_id", "") or ""
    roi_target = parsed.get("roi_target", "") or ""

    # Normalize token_id: map symbols to CoinGecko IDs
    if token_id:
        token_id = TOKEN_MAP.get(token_id.lower(), token_id.lower())

    logger.info("[intent_parser] intent=%-20s amount=%-6s token=%-20s roi=%s",
                intent, amount or "—", token_id or "—", roi_target or "—")

    return {
        "intent":     intent,
        "amount":     amount,
        "token_id":   token_id,
        "roi_target": roi_target,
    }
