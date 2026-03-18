"""
Conversational Customer Profiler
==================================
Conducts a multi-turn conversation to build the customer profile
before the main analysis pipeline runs.

Asks targeted questions across key domains:
  - Investment size / budget
  - Region / jurisdiction
  - Risk tolerance
  - Time horizon
  - Target return
  - Redemption / liquidity needs
  - Prior RWA / DeFi experience
"""

import json
import logging
from agents.utils import extract_json
from bedrock_client import BedrockClient

logger = logging.getLogger(__name__)

PROFILER_SYSTEM_PROMPT = """You are an experienced RWA investment advisor. You're having a relaxed, natural conversation with someone who wants a market analysis done for them. Your job is to get a clear picture of who they are as an investor.

You need to figure out:
- How much they want to invest and where they're based
- What kind of returns they're after and over what timeframe
- How they'd feel if things went sideways — would they hold, panic, or see it as an opportunity? (This is how you infer risk tolerance — NEVER ask "are you conservative or aggressive". Ask real questions like "if your portfolio dropped 15% next month, what would you do?" or "is growing the money the priority, or making sure you don't lose it?")
- How quickly they might need their money back
- Whether they've done anything like this before

Conversation style:
- Sound like a smart friend who knows finance, not a call center agent running through a script.
- React genuinely to what they say. If something they mention is interesting or unusual, riff on it briefly.
- Ask one focused question at a time. Keep your messages short — 2-3 sentences max.
- Build on what they've already told you. Never circle back to something they answered.
- Infer risk_tolerance from their answers — map to: "conservative", "moderate", or "aggressive". Never ask directly.
- Maximum 4 exchanges. On turn 4 wrap up and finalize.

Always respond with ONLY valid JSON:
{
  "message": "<your natural response — short, human, no bullet points>",
  "complete": <true|false>,
  "profile": {
    "budget": <float or null>,
    "region": "<string or null>",
    "risk_tolerance": "<conservative|moderate|aggressive or null — inferred, never asked>",
    "time_horizon_months": <int or null>,
    "expected_return_pct": <float or null>,
    "redemption_window": "<daily|weekly|monthly|quarterly|locked or null>",
    "experience": "<none|beginner|intermediate|advanced or null>"
  }
}

When complete is true, fill in sensible defaults for anything not covered."""


DEFAULTS = {
    "budget": 10000.0,
    "region": "US",
    "risk_tolerance": "moderate",
    "time_horizon_months": 12,
    "expected_return_pct": 10.0,
    "redemption_window": "monthly",
    "experience": "beginner",
}


class ConversationalProfiler:
    """Conducts a multi-turn Q&A to build a structured customer profile."""

    def __init__(self):
        self.bedrock = BedrockClient()
        self.history = []
        self.profile = {}
        self.complete = False
        self.turns = 0

    def start(self) -> str:
        """Send the opening greeting and first question."""
        opening = "Hey! Before I run the analysis, help me understand what you're working with — how much are you looking to put in, and where are you based?"
        self.history.append({"role": "assistant", "content": opening})
        return opening

    def respond(self, user_message: str) -> tuple:
        """
        Process user message, ask next question or finalize profile.
        Returns (message_to_display, is_complete).
        """
        self.history.append({"role": "user", "content": user_message})
        self.turns += 1

        # Build conversation context for LLM
        conversation = "\n".join(
            f"{'Client' if m['role'] == 'user' else 'Analyst'}: {m['content']}"
            for m in self.history
        )

        prompt = (
            f"Here is the conversation so far:\n\n{conversation}\n\n"
            "Based on what the client has shared, decide what to ask next "
            "(or finalize the profile if you have enough). "
            f"This is turn {self.turns} of at most 4."
        )

        raw = self.bedrock.send_message(prompt, system_prompt=PROFILER_SYSTEM_PROMPT)

        try:
            result = extract_json(raw)
        except (ValueError, json.JSONDecodeError):
            fallback = "Could you tell me more about your risk tolerance and how quickly you might need access to your funds?"
            self.history.append({"role": "assistant", "content": fallback})
            return fallback, False

        message = result.get("message", "")
        self.complete = result.get("complete", False)
        raw_profile = result.get("profile", {})

        # Merge non-null values into running profile
        for k, v in raw_profile.items():
            if v is not None:
                self.profile[k] = v

        # After 4 turns force completion
        if self.turns >= 4:
            self.complete = True

        self.history.append({"role": "assistant", "content": message})
        return message, self.complete

    def get_profile(self) -> dict:
        """Return the finalized profile with defaults applied."""
        profile = dict(DEFAULTS)
        profile.update({k: v for k, v in self.profile.items() if v is not None})

        # Normalize types
        profile["budget"] = float(profile["budget"])
        profile["time_horizon_months"] = int(profile["time_horizon_months"])
        profile["expected_return_pct"] = float(profile["expected_return_pct"])
        return profile
