import json
import logging
import os
import urllib.request
from urllib.error import URLError, HTTPError
import boto3
from datetime import datetime, timezone
import dateutil.parser

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get("LOG_LEVEL", "INFO"))

# Caching webhook URL
_SLACK_WEBHOOK_URL = None

def get_webhook_url():
    global _SLACK_WEBHOOK_URL
    if _SLACK_WEBHOOK_URL:
        return _SLACK_WEBHOOK_URL

    param_arn = os.environ.get("SLACK_WEBHOOK_PARAMETER_ARN")
    provider = os.environ.get("SLACK_WEBHOOK_PROVIDER", "ssm")

    if not param_arn:
        logger.warning("SLACK_WEBHOOK_PARAMETER_ARN not set. Returning None for local testing.")
        return None

    try:
        if provider == "ssm":
            ssm = boto3.client("ssm")
            # If it's an ARN, we need to extract the parameter name because
            # ssm:GetParameter only accepts ARNs for cross-account references.
            param_name = param_arn
            if param_arn.startswith("arn:aws:ssm:"):
                # Format: arn:aws:ssm:region:account-id:parameter/path/to/param
                # Split at ':parameter' and get the remaining path.
                parts = param_arn.split(":parameter", 1)
                if len(parts) > 1:
                    param_name = parts[1] # will contain /path/to/param
            
            try:
                response = ssm.get_parameter(Name=param_name, WithDecryption=True)
            except ssm.exceptions.ParameterNotFound:
                # Fallback: if the name was created without a leading slash but the ARN has it, try removing it
                if param_name.startswith("/"):
                    response = ssm.get_parameter(Name=param_name[1:], WithDecryption=True)
                else:
                    raise
            _SLACK_WEBHOOK_URL = response["Parameter"]["Value"]
        elif provider == "secretsmanager":
            sm = boto3.client("secretsmanager")
            response = sm.get_secret_value(SecretId=param_arn)
            _SLACK_WEBHOOK_URL = response.get("SecretString")
        else:
            raise ValueError(f"Unknown webhook provider: {provider}")
    except Exception as e:
        logger.error(f"Failed to fetch webhook URL from {provider}: {str(e)}")
        raise e
    
    return _SLACK_WEBHOOK_URL

def get_safe_resources(detail):
    """Safely extract resource information without leaking secrets."""
    # Redact potential secrets in request parameters
    req_params = detail.get("requestParameters", {})
    if not req_params:
        return "N/A"
    
    # Simple redaction logic
    safe_params = {}
    for k, v in req_params.items():
        if isinstance(k, str) and any(secret_term in k.lower() for secret_term in ["secret", "password", "token", "key", "credential"]):
            safe_params[k] = "[REDACTED]"
        else:
            safe_params[k] = v
            
    try:
        return json.dumps(safe_params, default=str)
    except Exception:
        return str(safe_params)

def parse_identity(user_identity):
    """Parse identity to determine who and caller context."""
    if not user_identity:
        return "Unknown", "Unknown"
        
    identity_type = user_identity.get("type", "Unknown")
    arn = user_identity.get("arn", "Unknown ARN")
    
    who_parts = [arn]
    
    session_context = user_identity.get("sessionContext", {})
    session_issuer = session_context.get("sessionIssuer", {})
    issuer_arn = session_issuer.get("arn")
    if issuer_arn:
        who_parts.append(f"(Issuer: {issuer_arn})")
        
    who = " ".join(who_parts)
    
    # Determine Context
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

def calculate_ttd(event_time_str, sent_timestamp_ms):
    """Calculate TTD metrics."""
    now = datetime.now(timezone.utc)
    detected_at_str = now.isoformat()
    
    processing_ttd_str = "Unknown"
    queue_age_str = "Unknown"
    
    try:
        if event_time_str:
            event_time = dateutil.parser.isoparse(event_time_str)
            processing_ttd_sec = (now - event_time).total_seconds()
            processing_ttd_str = f"{processing_ttd_sec:.1f}s"
    except Exception:
        pass
        
    try:
        if sent_timestamp_ms:
            sent_time = datetime.fromtimestamp(int(sent_timestamp_ms) / 1000.0, timezone.utc)
            queue_age_sec = (now - sent_time).total_seconds()
            queue_age_str = f"{queue_age_sec:.1f}s"
    except Exception:
        pass
        
    return detected_at_str, processing_ttd_str, queue_age_str

def format_slack_message(detail, sqs_attributes, rule_arn="audit-detection-rule"):
    """Format the alert contract for Slack."""
    
    event_name = detail.get("eventName", "Unknown")
    event_source = detail.get("eventSource", "Unknown")
    event_time = detail.get("eventTime", "Unknown")
    source_ip = detail.get("sourceIPAddress", "Unknown")
    region = detail.get("awsRegion", "Unknown")
    user_agent = detail.get("userAgent", "Unknown")
    
    error_code = detail.get("errorCode")
    error_message = detail.get("errorMessage")
    outcome = f"Failed ({error_code}: {error_message})" if error_code else "Success"
    
    event_id = detail.get("eventID", "Unknown")
    request_id = detail.get("requestID", "Unknown")
    
    user_identity = detail.get("userIdentity", {})
    who, caller_context = parse_identity(user_identity)
    
    resources = get_safe_resources(detail)
    
    sent_timestamp = sqs_attributes.get("SentTimestamp")
    detected_at, processing_ttd, queue_age = calculate_ttd(event_time, sent_timestamp)
    
    # Slack formatting (Block Kit or simple Markdown)
    text = (
        f"🚨 *AWS Audit Detection Alert* 🚨\n"
        f"*Nhóm phát hiện:* `{rule_arn}`\n"
        f"*Caller Context:* `{caller_context}`\n"
        f"*Ai:* `{who}`\n"
        f"*Làm gì:* `{event_source}` - `{event_name}`\n"
        f"*Khi nào:* `{event_time}`\n"
        f"*Từ đâu:* `{source_ip}` (Region: `{region}`) - `{user_agent}`\n"
        f"*Kết quả:* `{outcome}`\n"
        f"*Tài nguyên:* `{resources}`\n"
        f"*Tương quan:* EventID: `{event_id}`, RequestID: `{request_id}`\n"
        f"*TTD:* DetectedAt: `{detected_at}`, Processing TTD: `{processing_ttd}`, Queue Age: `{queue_age}`\n"
        f"*Hướng xử lý:* <https://wiki.internal/runbooks/audit-investigation|Investigation Runbook>"
    )
    
    return {"text": text}

def send_to_slack(webhook_url, payload):
    """Deliver message to Slack via HTTP POST. Fail on timeout or non-2xx."""
    if not webhook_url:
        logger.info("Webhook URL is empty. Skipping Slack delivery (likely running locally).")
        return
        
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(webhook_url, data=data, headers={'Content-Type': 'application/json'})
    
    try:
        # Timeout is 5 seconds. If this fails, we want it to bubble up to trigger SQS retry.
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.getcode() >= 300:
                raise Exception(f"Non-2xx response from Slack: {response.getcode()}")
    except urllib.error.HTTPError as e:
        logger.error(f"Slack delivery HTTP error: {e.code}")
        raise e
    except urllib.error.URLError as e:
        logger.error(f"Slack delivery URL error (Timeout/Connection): {e.reason}")
        raise e
    except Exception as e:
        logger.error(f"Slack delivery failed: {str(e)}")
        raise e

def lambda_handler(event, context):
    logger.info(f"Processing {len(event.get('Records', []))} SQS records.")
    
    # Fetch webhook once per batch/warm start
    webhook_url = get_webhook_url()
    
    for record in event.get("Records", []):
        try:
            body = record.get("body", "{}")
            eb_event = json.loads(body)
            
            detail = eb_event.get("detail", {})
            rule_arns = eb_event.get("resources", [])
            rule_arn = rule_arns[0] if rule_arns else "audit-detection-rule"
            
            # Extract safe info, do not log `eb_event` or `detail` directly
            event_id = detail.get("eventID", "Unknown")
            logger.info(f"Processing CloudTrail event: {event_id}")
            
            slack_payload = format_slack_message(detail, record.get("attributes", {}), rule_arn)
            
            send_to_slack(webhook_url, slack_payload)
            logger.info(f"Successfully processed CloudTrail event: {event_id}")
            
        except json.JSONDecodeError:
            logger.error("Failed to parse SQS body as JSON. Skipping invalid record.")
            # We don't raise here for JSON error to avoid poison message loop, 
            # unless we want DLQ to handle it. Actually raising allows DLQ to capture it.
            raise
        except Exception as e:
            logger.error("Error processing record. Raising exception to trigger SQS retry.")
            raise e

    return {"statusCode": 200, "body": "Success"}
