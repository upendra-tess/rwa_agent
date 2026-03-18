"""
Customer Risk Profiling Agent
==============================
First point of contact. Extracts the customer's investment profile from
natural language input using Claude/Bedrock.

Parameters extracted:
  - budget (USD)
  - region of residence
  - time_horizon_months
  - expected_return_pct
  - redemption_window (daily/weekly/monthly/quarterly/locked)
  - risk_tolerance (conservative/moderate/aggressive)
"""

import json
import logging
from agents.utils import extract_json

from bedrock_client import BedrockClient
from state import MultiAgentState
from data_sources import fetch_rwa_universe

logger = logging.getLogger(__name__)
bedrock = BedrockClient()

PROFILE_SYSTEM_PROMPT = """You are a Customer Risk Profiling Agent for an RWA (Real World Asset) investment platform.

Your job is to extract the customer's investment profile from their message. Extract these parameters:

1. budget: Investment budget in USD (float). Default to 10000 if not specified.
2. region: Region of residence. One of: "US", "EU", "UK", "APAC", "LATAM", "MENA", "GLOBAL". Default "US".
3. time_horizon_months: Investment time horizon in months (int). Default 12.
4. expected_return_pct: Expected annual return as percentage (float). Default 10.0.
5. redemption_window: How quickly they need liquidity access. One of: "daily", "weekly", "monthly", "quarterly", "locked". Default "monthly".
6. risk_tolerance: One of: "conservative", "moderate", "aggressive". Infer from context:
   - conservative: mentions safety, low risk, preservation, stable, treasury, fixed income
   - moderate: balanced approach, mentions both growth and safety, diversified
   - aggressive: high returns, growth, willing to take risk, crypto-native, DeFi

Return ONLY valid JSON (no markdown, no explanation):
{
  "budget": <float>,
  "region": "<string>",
  "time_horizon_months": <int>,
  "expected_return_pct": <float>,
  "redemption_window": "<string>",
  "risk_tolerance": "<string>"
}"""


def customer_profiling_agent(state: MultiAgentState) -> dict:
    """Extract customer profile from user input using LLM, or use pre-built profile from conversation."""
    # If profile was already built via conversational profiler, skip LLM parsing
    existing_profile = state.get("customer_profile", {})
    if existing_profile.get("_from_conversation"):
        profile = existing_profile
        logger.info("[customer_profiling] Using conversational profile: %s", profile)
    else:
        user_input = state.get("user_input", "")
        logger.info("[customer_profiling] Processing: %s", user_input[:100])

        prompt = f"Extract the customer investment profile from this message:\n\n\"{user_input}\""
        raw = bedrock.send_message(prompt, system_prompt=PROFILE_SYSTEM_PROMPT)

        try:
            profile = extract_json(raw)
        except Exception as e:
            logger.warning("[customer_profiling] Failed to parse: %s", raw[:200])
            profile = {}

        # Apply defaults for missing fields
        defaults = {
            "budget": 10000.0,
            "region": "US",
            "time_horizon_months": 12,
            "expected_return_pct": 10.0,
            "redemption_window": "monthly",
            "risk_tolerance": "moderate",
        }
        for key, default in defaults.items():
            if key not in profile or profile[key] is None:
                profile[key] = default

        # Ensure correct types
        profile["budget"] = float(profile["budget"])
        profile["time_horizon_months"] = int(profile["time_horizon_months"])
        profile["expected_return_pct"] = float(profile["expected_return_pct"])

    logger.info(
        "[customer_profiling] Profile: budget=$%.0f region=%s horizon=%dmo "
        "return=%.1f%% redemption=%s risk=%s",
        profile.get("budget", 0), profile.get("region", "?"),
        profile.get("time_horizon_months", 0), profile.get("expected_return_pct", 0),
        profile.get("redemption_window", "?"), profile.get("risk_tolerance", "?"),
    )

    # Fetch the live RWA universe (single source of truth for all downstream agents)
    logger.info("[customer_profiling] Fetching live RWA universe from DefiLlama...")
    rwa_universe = fetch_rwa_universe(min_tvl_usd=1_000_000)
    logger.info("[customer_profiling] RWA universe: %d assets loaded", len(rwa_universe))

    return {"customer_profile": profile, "rwa_universe": rwa_universe}
