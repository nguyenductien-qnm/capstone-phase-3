import json
import os
import urllib.error
import pytest
from unittest.mock import patch, MagicMock
import importlib.util
import sys

# Dynamically load the handler since "lambda" is a reserved keyword
module_name = "handler"
file_path = os.path.join(os.path.dirname(__file__), "../lambda/handler.py")
spec = importlib.util.spec_from_file_location(module_name, file_path)
handler = importlib.util.module_from_spec(spec)
sys.modules[module_name] = handler
spec.loader.exec_module(handler)

parse_identity = handler.parse_identity
get_safe_resources = handler.get_safe_resources
calculate_ttd = handler.calculate_ttd
format_slack_message = handler.format_slack_message
send_to_slack = handler.send_to_slack
lambda_handler = handler.lambda_handler
get_webhook_url = handler.get_webhook_url

@pytest.fixture
def iam_create_user_event():
    with open(os.path.join(os.path.dirname(__file__), "fixtures/event_iam_create_user.json")) as f:
        return json.load(f)

@pytest.fixture
def eks_automation_event():
    with open(os.path.join(os.path.dirname(__file__), "fixtures/event_eks_automation.json")) as f:
        return json.load(f)

@pytest.fixture
def root_login_event():
    with open(os.path.join(os.path.dirname(__file__), "fixtures/event_root_login.json")) as f:
        return json.load(f)

@pytest.fixture
def sqs_payload():
    with open(os.path.join(os.path.dirname(__file__), "fixtures/sqs_payload.json")) as f:
        return json.load(f)

def test_parse_identity_iam(iam_create_user_event):
    who, context = parse_identity(iam_create_user_event["detail"]["userIdentity"])
    assert "arn:aws:iam::111122223333:user/test-admin" in who
    assert context == "Human (IAM User)"

def test_parse_identity_eks_automation(eks_automation_event):
    who, context = parse_identity(eks_automation_event["detail"]["userIdentity"])
    assert "gha-actor" in who
    assert "(Issuer: arn:aws:iam::111122223333:role/GitHubTerraformSandboxRole)" in who
    assert context == "Automation (GitHub Actions)"

def test_parse_identity_root(root_login_event):
    who, context = parse_identity(root_login_event["detail"]["userIdentity"])
    assert "arn:aws:iam::111122223333:root" in who
    assert context == "Root Account"

def test_parse_identity_missing():
    who, context = parse_identity({})
    assert who == "Unknown"
    assert context == "Unknown"
    
def test_parse_identity_aws_service():
    ui = {
        "type": "AWSService",
        "invokedBy": "cloudtrail.amazonaws.com"
    }
    who, context = parse_identity(ui)
    assert who == "cloudtrail.amazonaws.com"
    assert context == "AWS Service Automation"

def test_get_safe_resources(sqs_payload):
    # sqs_payload has requestParameters with userName and secretToken
    eb_event = json.loads(sqs_payload["Records"][0]["body"])
    detail = eb_event["detail"]
    resources = get_safe_resources(detail)
    resources_dict = json.loads(resources)
    assert resources_dict["userName"] == "backdoor-user"
    assert resources_dict["secretToken"] == "[REDACTED]"

def test_missing_fields():
    # Provide a malformed detail to ensure format_slack_message doesn't crash (fails open)
    detail = {"eventName": "UnknownAction"}
    attributes = {}
    result = format_slack_message(detail, attributes)
    assert "UnknownAction" in result["text"]
    assert "Unknown" in result["text"]

@patch("urllib.request.urlopen")
def test_send_to_slack_success(mock_urlopen):
    mock_response = MagicMock()
    mock_response.getcode.return_value = 200
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    # Should not raise exception
    send_to_slack("https://hooks.slack.com/services/test", {"text": "hello"})
    mock_urlopen.assert_called_once()

@patch("urllib.request.urlopen")
def test_send_to_slack_timeout(mock_urlopen):
    mock_urlopen.side_effect = urllib.error.URLError("Timeout")
    
    with pytest.raises(urllib.error.URLError):
        send_to_slack("https://hooks.slack.com/services/test", {"text": "hello"})

@patch("urllib.request.urlopen")
def test_send_to_slack_non_2xx(mock_urlopen):
    mock_response = MagicMock()
    mock_response.getcode.return_value = 403
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    with pytest.raises(Exception, match="Non-2xx response"):
        send_to_slack("https://hooks.slack.com/services/test", {"text": "hello"})

@patch("handler.send_to_slack")
@patch("handler.get_webhook_url")
def test_lambda_handler_success(mock_get_webhook, mock_send, sqs_payload):
    mock_get_webhook.return_value = "https://test.webhook"
    
    response = lambda_handler(sqs_payload, None)
    
    assert response["statusCode"] == 200
    mock_send.assert_called_once()
    
    # Inspect the payload sent to Slack to ensure idempotency tracking (eventID) is present
    args, kwargs = mock_send.call_args
    slack_msg = args[1]["text"]
    assert "evt-123" in slack_msg
    assert "req-123" in slack_msg

@patch("handler.send_to_slack")
@patch("handler.get_webhook_url")
def test_lambda_handler_delivery_failure(mock_get_webhook, mock_send, sqs_payload):
    mock_get_webhook.return_value = "https://test.webhook"
    mock_send.side_effect = Exception("Simulated Failure")
    
    with pytest.raises(Exception, match="Simulated Failure"):
        lambda_handler(sqs_payload, None)

@patch("boto3.client")
@patch.dict(os.environ, {"SLACK_WEBHOOK_PARAMETER_ARN": "test-arn", "SLACK_WEBHOOK_PROVIDER": "ssm"})
def test_get_webhook_url_ssm(mock_boto):
    mock_ssm = MagicMock()
    mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "https://ssm.webhook"}}
    mock_boto.return_value = mock_ssm
    
    handler._SLACK_WEBHOOK_URL = None # reset cache
    url = handler.get_webhook_url()
    assert url == "https://ssm.webhook"
    mock_boto.assert_called_with("ssm")

@patch("boto3.client")
@patch.dict(os.environ, {"SLACK_WEBHOOK_PARAMETER_ARN": "test-secret", "SLACK_WEBHOOK_PROVIDER": "secretsmanager"})
def test_get_webhook_url_secretsmanager(mock_boto):
    mock_sm = MagicMock()
    mock_sm.get_secret_value.return_value = {"SecretString": "https://sm.webhook"}
    mock_boto.return_value = mock_sm
    
    handler._SLACK_WEBHOOK_URL = None # reset cache
    url = handler.get_webhook_url()
    assert url == "https://sm.webhook"
    mock_boto.assert_called_with("secretsmanager")
