"""Bedrock client factory with optional cross-account credentials.

The deployment can provide dedicated Bedrock credentials via:
- BEDROCK_AWS_ACCESS_KEY_ID
- BEDROCK_AWS_SECRET_ACCESS_KEY
- BEDROCK_AWS_SESSION_TOKEN (optional)

If both access key and secret key are absent, boto3 falls back to the normal
provider chain (Pod Identity / IRSA / node role / local profile).
"""

from __future__ import annotations

import logging
import os

import boto3

logger = logging.getLogger(__name__)


def create_bedrock_runtime_client(*, region_name: str, config=None):
    kwargs = {
        "service_name": "bedrock-runtime",
        "region_name": region_name,
    }
    if config is not None:
        kwargs["config"] = config

    access_key = os.environ.get("BEDROCK_AWS_ACCESS_KEY_ID")
    secret_key = os.environ.get("BEDROCK_AWS_SECRET_ACCESS_KEY")
    session_token = os.environ.get("BEDROCK_AWS_SESSION_TOKEN")

    if access_key and secret_key:
        kwargs["aws_access_key_id"] = access_key
        kwargs["aws_secret_access_key"] = secret_key
        if session_token:
            kwargs["aws_session_token"] = session_token
        logger.info("Using explicit BEDROCK_AWS_* credentials for Bedrock runtime")
    elif access_key or secret_key:
        logger.warning(
            "Incomplete BEDROCK_AWS_* credentials; falling back to default AWS provider chain"
        )

    return boto3.client(**kwargs)
