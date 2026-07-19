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
from botocore.credentials import RefreshableCredentials
from botocore.session import get_session

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

        def refresh_credentials():
            credentials = sts.assume_role(**assume_role_kwargs)["Credentials"]
            return {
                "access_key": credentials["AccessKeyId"],
                "secret_key": credentials["SecretAccessKey"],
                "token": credentials["SessionToken"],
                "expiry_time": credentials["Expiration"].isoformat(),
            }

        botocore_session = get_session()
        botocore_session._credentials = RefreshableCredentials.create_from_metadata(
            metadata=refresh_credentials(),
            refresh_using=refresh_credentials,
            method="sts-assume-role",
        )
        session = boto3.Session(botocore_session=botocore_session)
        logger.info("Using refreshable assumed-role credentials for Bedrock runtime")
        return session.client("bedrock-runtime", region_name=region_name, config=config)

    kwargs = {"service_name": "bedrock-runtime", "region_name": region_name}
    if config is not None:
        kwargs["config"] = config

    logger.info("Using default AWS provider chain for Bedrock runtime")
    return boto3.client(**kwargs)
