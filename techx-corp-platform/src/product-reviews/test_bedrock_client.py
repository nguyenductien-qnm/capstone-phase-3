from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
from unittest.mock import Mock

import pytest


CLIENT_MODULES = [
    Path(__file__).with_name("bedrock_client.py"),
    Path(__file__).parents[1] / "shopping-copilot" / "bedrock_client.py",
]


def load_module(path):
    spec = importlib.util.spec_from_file_location(f"test_{path.parent.name}_bedrock_client", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("module_path", CLIENT_MODULES)
def test_cross_account_credentials_refresh(module_path, monkeypatch):
    module = load_module(module_path)
    expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    sts = Mock()
    sts.assume_role.side_effect = [
        {
            "Credentials": {
                "AccessKeyId": "initial-access-key",
                "SecretAccessKey": "initial-secret-key",
                "SessionToken": "initial-token",
                "Expiration": expiration,
            }
        },
        {
            "Credentials": {
                "AccessKeyId": "refreshed-access-key",
                "SecretAccessKey": "refreshed-secret-key",
                "SessionToken": "refreshed-token",
                "Expiration": expiration + timedelta(hours=1),
            }
        },
    ]
    botocore_session = Mock()
    assumed_session = Mock()
    bedrock_client = assumed_session.client.return_value

    monkeypatch.setenv("BEDROCK_AWS_ROLE_ARN", "arn:aws:iam::123456789012:role/bedrock")
    monkeypatch.setattr(module.boto3, "client", Mock(return_value=sts))
    monkeypatch.setattr(module.boto3, "Session", Mock(return_value=assumed_session))
    monkeypatch.setattr(module, "get_session", Mock(return_value=botocore_session))

    client = module.create_bedrock_runtime_client(region_name="us-east-1")
    refreshed = botocore_session._credentials._refresh_using()

    assert client is bedrock_client
    assert refreshed["access_key"] == "refreshed-access-key"
    assert sts.assume_role.call_count == 2
    module.boto3.Session.assert_called_once_with(botocore_session=botocore_session)
    assumed_session.client.assert_called_once_with(
        "bedrock-runtime", region_name="us-east-1", config=None
    )
