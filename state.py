from typing import TypedDict, Optional


class AgentState(TypedDict):
    # User input
    user_input:   str

    # Parsed intent fields
    intent:       str
    amount:       Optional[str]   # ETH or USD amount
    user_address: str
    token_id:     Optional[str]   # CoinGecko token ID (e.g. "ondo-finance")
    roi_target:   Optional[str]   # ROI % target as string (e.g. "20")

    # Output
    result:       str
