"""Shared utilities for agent JSON parsing."""

import json
import re


def extract_json(text: str):
    """
    Robustly extract a JSON object or array from an LLM response.
    Handles markdown code fences, preamble text, and trailing content.
    """
    text = text.strip()

    # Try direct parse first (cleanest case)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the outermost JSON object {...} or array [...]
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

    raise ValueError(f"No valid JSON found in response (first 500 chars): {text[:500]}")
