# ============================================================
# bedrock_client.py — AWS Bedrock LLM Client
# ============================================================
# A lightweight wrapper that calls AWS Bedrock's Converse API
# using a single API key via Bearer-token authentication.
#
# Endpoint pattern:
#   https://bedrock-runtime.{region}.amazonaws.com
#         /model/{modelId}/converse
# ============================================================

import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables from the .env file
load_dotenv()


class BedrockClient:
    """
    Sends messages to AWS Bedrock and returns the LLM response text.

    Usage
    -----
    >>> client = BedrockClient()
    >>> reply = client.send_message("What is Ethereum?")
    >>> print(reply)
    """

    def __init__(self):
        # ---- Read configuration from environment ----
        self.api_key = os.getenv("BEDROCK_API_KEY")          # Bearer token
        self.model_id = os.getenv("BEDROCK_MODEL_ID")        # e.g. anthropic.claude-3-haiku-...
        self.region = os.getenv("AWS_REGION", "us-east-1")    # AWS region

        # ---- Build the endpoint URL ----
        self.endpoint = (
            f"https://bedrock-runtime.{self.region}.amazonaws.com"
            f"/model/{self.model_id}/converse"
        )

    # ---------------------------------------------------------
    # Public method – call the LLM with a user message
    # ---------------------------------------------------------
    def send_message(self, user_message: str) -> str:
        """
        Send a single user message to Bedrock and return the
        assistant's reply as a plain string.

        Parameters
        ----------
        user_message : str
            The text you want the LLM to process.

        Returns
        -------
        str
            The assistant's response text.
        """

        # ---- HTTP headers (Bearer auth) ----
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        # ---- Request body (Converse API format) ----
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": user_message}],
                }
            ],
        }

        # ---- Make the API call ----
        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=30,            # 30-second timeout
            )
            response.raise_for_status()  # Raise on 4xx / 5xx

            # ---- Parse the response ----
            data = response.json()

            # The Converse API nests the text inside:
            #   output → message → content → [0] → text
            assistant_text = (
                data.get("output", {})
                    .get("message", {})
                    .get("content", [{}])[0]
                    .get("text", "")
            )
            return assistant_text

        except requests.exceptions.RequestException as err:
            # Return a clear error so the caller can handle it
            return f"[Bedrock API Error] {err}"
