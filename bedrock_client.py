# ============================================================
# bedrock_client.py — AWS Bedrock LLM Client
# ============================================================
# Uses boto3 with AWS SigV4 authentication (standard Bedrock auth).
# Requires AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY in .env
# ============================================================

import os
import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()


class BedrockClient:
    """
    Sends messages to AWS Bedrock via the Converse API using boto3.

    Usage
    -----
    >>> client = BedrockClient()
    >>> reply = client.send_message("What is Ethereum?")
    >>> print(reply)
    """

    def __init__(self):
        self.model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-opus-4-6-v1:1m")
        self.region = os.getenv("AWS_REGION", "us-east-1")

        session = boto3.Session(
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            region_name=self.region,
        )
        self.client = session.client(
            "bedrock-runtime",
            config=Config(read_timeout=60, connect_timeout=10),
        )

    def send_message(self, user_message: str, system_prompt: str = None) -> str:
        """
        Send a user message to Bedrock and return the assistant's reply.
        """
        kwargs = {
            "modelId": self.model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": user_message}],
                }
            ],
        }
        if system_prompt:
            kwargs["system"] = [{"text": system_prompt}]

        try:
            response = self.client.converse(**kwargs)
            return (
                response.get("output", {})
                        .get("message", {})
                        .get("content", [{}])[0]
                        .get("text", "")
            )
        except Exception as err:
            return f"[Bedrock Error] {err}"
