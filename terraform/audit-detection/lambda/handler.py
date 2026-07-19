import html
import json
import logging
import os
import time
from datetime import datetime, timezone
from urllib import error, parse, request

import boto3
from botocore.exceptions import ClientError


logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

_SLACK_WEBHOOK_URL = None
_IDEMPOTENCY_TABLE = None
_SECRET_TERMS = (
    "secret",
    "password",
    "token",
    "credential",
    "accesskey",
    "privatekey",
    "apikey",
    "authorization",
    "webhook",
)
_SLACK_WEBHOOK_HOSTS = {"hooks.slack.com", "hooks.slack-gov.com"}


def _validate_webhook_url(webhook_url):
    parsed = parse.urlparse(webhook_url)
    if parsed.scheme != "https" or parsed.hostname not in _SLACK_WEBHOOK_HOSTS:
        raise ValueError("Slack webhook must use HTTPS and an approved Slack webhook host")
    return webhook_url


def get_webhook_url():
    """Read and cache the Slack webhook without logging its value."""
    global _SLACK_WEBHOOK_URL
    if _SLACK_WEBHOOK_URL:
        return _SLACK_WEBHOOK_URL

    parameter_arn = os.environ.get("SLACK_WEBHOOK_PARAMETER_ARN")
    provider = os.environ.get("SLACK_WEBHOOK_PROVIDER", "ssm")
    if not parameter_arn:
        raise RuntimeError("SLACK_WEBHOOK_PARAMETER_ARN is required")

    try:
        if provider == "ssm":
            ssm = boto3.client("ssm")
            parameter_name = parameter_arn
            if ":ssm:" in parameter_arn and ":parameter" in parameter_arn:
                parameter_name = parameter_arn.split(":parameter", 1)[1]

            try:
                response = ssm.get_parameter(Name=parameter_name, WithDecryption=True)
            except ssm.exceptions.ParameterNotFound:
                if not parameter_name.startswith("/"):
                    raise
                response = ssm.get_parameter(
                    Name=parameter_name.removeprefix("/"), WithDecryption=True
                )
            webhook_url = response["Parameter"]["Value"]
        elif provider == "secretsmanager":
            secrets_manager = boto3.client("secretsmanager")
            response = secrets_manager.get_secret_value(SecretId=parameter_arn)
            webhook_url = response.get("SecretString")
            if webhook_url is None and response.get("SecretBinary") is not None:
                secret_binary = response["SecretBinary"]
                webhook_url = (
                    secret_binary.decode("utf-8")
                    if isinstance(secret_binary, bytes)
                    else str(secret_binary)
                )

            if webhook_url:
                try:
                    secret_document = json.loads(webhook_url)
                    if isinstance(secret_document, dict):
                        webhook_url = secret_document.get("webhook_url") or secret_document.get(
                            "url"
                        )
                except json.JSONDecodeError:
                    pass
        else:
            raise ValueError(f"Unknown webhook provider: {provider}")
    except Exception:
        logger.exception("Failed to fetch Slack webhook from %s", provider)
        raise

    if not webhook_url:
        raise RuntimeError("Slack webhook secret is empty")

    _SLACK_WEBHOOK_URL = _validate_webhook_url(webhook_url.strip())
    return _SLACK_WEBHOOK_URL


def _sanitize_value(value, key="", depth=0):
    if any(term in key.lower().replace("_", "") for term in _SECRET_TERMS):
        return "[REDACTED]"
    if depth >= 6:
        return "[MAX_DEPTH_REACHED]"
    if isinstance(value, dict):
        return {
            str(child_key): _sanitize_value(child_value, str(child_key), depth + 1)
            for child_key, child_value in list(value.items())[:50]
        }
    if isinstance(value, list):
        return [_sanitize_value(item, key, depth + 1) for item in value[:50]]
    if isinstance(value, str) and len(value) > 1000:
        return f"{value[:1000]}...[TRUNCATED]"
    return value


def get_safe_resources(detail):
    """Return a bounded, recursively redacted request-parameter summary."""
    request_parameters = detail.get("requestParameters")
    if not request_parameters:
        return "N/A"

    try:
        result = json.dumps(
            _sanitize_value(request_parameters),
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
    except (TypeError, ValueError):
        result = "[UNSERIALIZABLE_REQUEST_PARAMETERS]"
    return result if len(result) <= 3000 else f"{result[:3000]}...[TRUNCATED]"


def parse_identity(user_identity):
    """Extract the principal and a human-readable caller context."""
    if not user_identity:
        return "Unknown", "Unknown"

    identity_type = user_identity.get("type", "Unknown")
    arn = user_identity.get("arn", "Unknown ARN")
    who_parts = [arn]

    session_issuer = user_identity.get("sessionContext", {}).get("sessionIssuer", {})
    issuer_arn = session_issuer.get("arn")
    if issuer_arn:
        who_parts.append(f"(Issuer: {issuer_arn})")

    who = " ".join(who_parts)
    caller_context = identity_type
    if identity_type == "AssumedRole":
        if "gha-" in arn or "github" in arn.lower():
            caller_context = "Automation (GitHub Actions)"
        elif "break-glass" in arn.lower() or "audit-admin" in arn.lower():
            caller_context = "Break-Glass Role"
        else:
            caller_context = "Assumed Role"
    elif identity_type == "Root":
        caller_context = "Root Account"
    elif identity_type == "IAMUser":
        caller_context = "Human (IAM User)"
    elif identity_type == "AWSService":
        caller_context = "AWS Service Automation"
        who = user_identity.get("invokedBy", arn)

    return who, caller_context


def _parse_event_time(event_time_string):
    if not event_time_string:
        return None
    parsed_time = datetime.fromisoformat(event_time_string.replace("Z", "+00:00"))
    return parsed_time.replace(tzinfo=parsed_time.tzinfo or timezone.utc)


def calculate_ttd(event_time_string, sent_timestamp_ms):
    """Calculate processing TTD and current queue age using UTC timestamps."""
    now = datetime.now(timezone.utc)
    detected_at = now.isoformat()
    processing_ttd = "Unknown"
    queue_age = "Unknown"

    try:
        event_time = _parse_event_time(event_time_string)
        if event_time:
            processing_ttd = f"{max(0, (now - event_time).total_seconds()):.1f}s"
    except (TypeError, ValueError):
        logger.warning("CloudTrail eventTime is invalid")

    try:
        if sent_timestamp_ms:
            sent_time = datetime.fromtimestamp(
                int(sent_timestamp_ms) / 1000.0, timezone.utc
            )
            queue_age = f"{max(0, (now - sent_time).total_seconds()):.1f}s"
    except (TypeError, ValueError, OSError):
        logger.warning("SQS SentTimestamp is invalid")

    return detected_at, processing_ttd, queue_age


def _slack_safe(value, limit=1000):
    rendered = str(value if value is not None else "Unknown")
    rendered = (
        html.escape(rendered, quote=False)
        .replace("`", "'")
        .replace("\r", " ")
        .replace("\n", " ")
    )
    return rendered if len(rendered) <= limit else f"{rendered[:limit]}...[TRUNCATED]"


def format_slack_message(
    detail,
    sqs_attributes,
    detection_category="unknown_detection",
    rule_key="unknown_rule",
):
    """Format the audit alert contract as a bounded Slack message."""
    event_name = detail.get("eventName", "Unknown")
    event_source = detail.get("eventSource", "Unknown")
    event_time = detail.get("eventTime", "Unknown")
    source_ip = detail.get("sourceIPAddress", "Unknown")
    region = detail.get("awsRegion", "Unknown")
    user_agent = detail.get("userAgent", "Unknown")

    error_code = detail.get("errorCode")
    error_message = detail.get("errorMessage")
    console_result = (detail.get("responseElements") or {}).get("ConsoleLogin")
    if error_code:
        outcome = f"Failed ({error_code}: {error_message or 'No error message'})"
    elif console_result and console_result != "Success":
        outcome = f"Failed ({console_result})"
    else:
        outcome = "Success"

    mfa_used = (detail.get("additionalEventData") or {}).get("MFAUsed", "N/A")
    event_id = detail.get("eventID", "Unknown")
    request_id = detail.get("requestID", "Unknown")
    who, caller_context = parse_identity(detail.get("userIdentity", {}))
    resources = get_safe_resources(detail)
    detected_at, processing_ttd, queue_age = calculate_ttd(
        event_time, sqs_attributes.get("SentTimestamp")
    )

    text = (
        "🚨 *AWS Audit Detection Alert* 🚨\n"
        f"*Nhóm phát hiện:* `{_slack_safe(detection_category)}` "
        f"(rule: `{_slack_safe(rule_key)}`)\n"
        f"*Caller Context:* `{_slack_safe(caller_context)}`\n"
        f"*Ai:* `{_slack_safe(who, 1500)}`\n"
        f"*Làm gì:* `{_slack_safe(event_source)}` - `{_slack_safe(event_name)}`\n"
        f"*Khi nào:* `{_slack_safe(event_time)}`\n"
        f"*Từ đâu:* `{_slack_safe(source_ip)}` (Region: `{_slack_safe(region)}`) - "
        f"`{_slack_safe(user_agent, 500)}`\n"
        f"*Kết quả:* `{_slack_safe(outcome)}` (MFA: `{_slack_safe(mfa_used)}`)\n"
        f"*Tài nguyên:* `{_slack_safe(resources, 3500)}`\n"
        f"*Tương quan:* EventID: `{_slack_safe(event_id)}`, "
        f"RequestID: `{_slack_safe(request_id)}`\n"
        f"*TTD:* DetectedAt: `{_slack_safe(detected_at)}`, "
        f"Processing TTD: `{_slack_safe(processing_ttd)}`, "
        f"Queue Age: `{_slack_safe(queue_age)}`\n"
        "*Hướng xử lý:* Investigation runbook"
    )
    return {"text": text[:12000]}


def send_to_slack(webhook_url, payload):
    """POST to Slack and raise on every delivery failure so SQS can retry."""
    if not webhook_url:
        raise RuntimeError("Slack webhook URL is empty")
    _validate_webhook_url(webhook_url)

    request_body = json.dumps(payload).encode("utf-8")
    slack_request = request.Request(
        webhook_url,
        data=request_body,
        headers={"Content-Type": "application/json", "User-Agent": "audit-detection/1.0"},
        method="POST",
    )
    try:
        with request.urlopen(slack_request, timeout=5) as response:
            if not 200 <= response.getcode() < 300:
                raise RuntimeError(f"Non-2xx response from Slack: {response.getcode()}")
    except error.HTTPError as exc:
        logger.error("Slack delivery HTTP error: %s", exc.code)
        raise
    except error.URLError as exc:
        logger.error("Slack delivery connection error: %s", exc.reason)
        raise


def ping_slack(webhook_url):
    """Perform an explicit Slack delivery check; failures are Lambda failures."""
    send_to_slack(
        webhook_url,
        {"text": "🔍 *[HEALTH CHECK] Audit Detection Slack delivery succeeded.*"},
    )
    return {"statusCode": 200, "body": "Slack ping check succeeded"}


def _get_idempotency_table():
    global _IDEMPOTENCY_TABLE
    table_name = os.environ.get("IDEMPOTENCY_TABLE_NAME")
    if not table_name:
        return None
    if _IDEMPOTENCY_TABLE is None:
        _IDEMPOTENCY_TABLE = boto3.resource("dynamodb").Table(table_name)
    return _IDEMPOTENCY_TABLE


def acquire_event_lock(event_id, message_id):
    """Acquire an idempotency lease; return False for a competing/completed event."""
    table = _get_idempotency_table()
    if table is None or not event_id or event_id == "Unknown":
        return True

    now = int(time.time())
    lease_seconds = int(os.environ.get("IDEMPOTENCY_LEASE_SECONDS", "300"))
    retention_seconds = int(os.environ.get("IDEMPOTENCY_RETENTION_SECONDS", "86400"))
    try:
        table.put_item(
            Item={
                "event_id": event_id,
                "status": "IN_PROGRESS",
                "owner_message_id": message_id,
                "lease_expires_at": now + lease_seconds,
                "expires_at": now + retention_seconds,
            },
            ConditionExpression=(
                "attribute_not_exists(event_id) OR lease_expires_at < :now OR "
                "(#status = :in_progress AND owner_message_id = :owner)"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":now": now,
                ":in_progress": "IN_PROGRESS",
                ":owner": message_id,
            },
        )
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            logger.info("Skipping duplicate CloudTrail event: %s", event_id)
            return False
        raise


def complete_event(event_id, message_id):
    table = _get_idempotency_table()
    if table is None or not event_id or event_id == "Unknown":
        return
    retention_seconds = int(os.environ.get("IDEMPOTENCY_RETENTION_SECONDS", "86400"))
    table.update_item(
        Key={"event_id": event_id},
        UpdateExpression="SET #status = :completed, expires_at = :expires REMOVE lease_expires_at",
        ConditionExpression="owner_message_id = :owner",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":completed": "COMPLETED",
            ":expires": int(time.time()) + retention_seconds,
            ":owner": message_id,
        },
    )


def release_event_lock(event_id, message_id):
    table = _get_idempotency_table()
    if table is None or not event_id or event_id == "Unknown":
        return
    try:
        table.delete_item(
            Key={"event_id": event_id},
            ConditionExpression="owner_message_id = :owner AND #status = :in_progress",
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":owner": message_id,
                ":in_progress": "IN_PROGRESS",
            },
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise


def _unwrap_eventbridge_message(message_body):
    envelope = json.loads(message_body)
    if isinstance(envelope.get("event"), dict):
        return (
            envelope["event"],
            envelope.get("detectionCategory", "unknown_detection"),
            envelope.get("ruleKey", "unknown_rule"),
        )
    return envelope, "legacy_event", "legacy_rule"


def lambda_handler(event, context):
    if isinstance(event, dict) and (
        event.get("action") == "ping" or event.get("type") == "ping"
    ):
        return ping_slack(get_webhook_url())

    records = event.get("Records", []) if isinstance(event, dict) else []
    if not records:
        raise ValueError("Expected at least one SQS record")

    logger.info("Processing %d SQS record(s)", len(records))
    webhook_url = get_webhook_url()

    for record in records:
        eventbridge_event, detection_category, rule_key = _unwrap_eventbridge_message(
            record.get("body", "{}")
        )
        detail = eventbridge_event.get("detail", {})
        event_id = detail.get("eventID", "Unknown")
        message_id = record.get("messageId", "unknown-message")
        logger.info("Processing CloudTrail event: %s", event_id)

        if not acquire_event_lock(event_id, message_id):
            continue

        slack_payload = format_slack_message(
            detail,
            record.get("attributes", {}),
            detection_category,
            rule_key,
        )
        try:
            send_to_slack(webhook_url, slack_payload)
        except Exception:
            try:
                release_event_lock(event_id, message_id)
            except Exception:
                logger.exception("Could not release the idempotency lock")
            logger.exception("Slack delivery failed; returning the SQS message for retry")
            raise

        complete_event(event_id, message_id)
        logger.info("Successfully processed CloudTrail event: %s", event_id)

    return {"statusCode": 200, "body": "Success"}
