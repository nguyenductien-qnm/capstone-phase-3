"""Bedrock client factory for IRSA / optional cross-account role.

The service normally relies on the default AWS provider chain, so EKS can
inject credentials through IRSA / Pod Identity without static keys.

For a dedicated Bedrock account, set BEDROCK_AWS_ROLE_ARN. The pod's IRSA role
must have sts:AssumeRole permission on that target role, and the target role
must allow bedrock:InvokeModel in the Bedrock account.
"""

from __future__ import annotations

import logging
import os

import boto3

logger = logging.getLogger(__name__)


def create_bedrock_runtime_client(*, region_name: str, config=None):
    role_arn = os.environ.get("BEDROCK_AWS_ROLE_ARN")
    if role_arn:
        session_name = os.environ.get("BEDROCK_AWS_ROLE_SESSION_NAME", "product-reviews-bedrock")
        assume_role_kwargs = {
            "RoleArn": role_arn,
            "RoleSessionName": session_name,
        }
        external_id = os.environ.get("BEDROCK_AWS_EXTERNAL_ID")
        if external_id:
            assume_role_kwargs["ExternalId"] = external_id

        sts = boto3.client("sts")
        response = sts.assume_role(**assume_role_kwargs)
        credentials = response["Credentials"]
        session = boto3.Session(
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"],
        )
        logger.info("Using IRSA to assume BEDROCK_AWS_ROLE_ARN for Bedrock runtime")
        return session.client("bedrock-runtime", region_name=region_name, config=config)

    kwargs = {"service_name": "bedrock-runtime", "region_name": region_name}
    if config is not None:
        kwargs["config"] = config

    logger.info("Using default AWS provider chain for Bedrock runtime")
    return boto3.client(**kwargs)
