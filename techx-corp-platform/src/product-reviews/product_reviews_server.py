#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


# Python
import os
import json
from concurrent import futures
import random

# Pip
import grpc
from opentelemetry import trace, metrics
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
    OTLPLogExporter,
)
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import Status, StatusCode

# Local
import logging
import demo_pb2
import demo_pb2_grpc
from grpc_health.v1 import health_pb2
from grpc_health.v1 import health_pb2_grpc
from database import fetch_product_reviews, fetch_product_reviews_from_db, fetch_avg_product_review_score_from_db

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider

from metrics import (
    init_metrics
)

# OpenAI
from openai import OpenAI

import boto3
from botocore.exceptions import ClientError
import redis
from datetime import datetime, timezone

from google.protobuf.json_format import MessageToJson, MessageToDict


llm_host = None
llm_port = None
llm_mock_url = None
llm_base_url = None
llm_api_key = None
llm_model = None

# --- Define the tool for the OpenAI API ---
valkey_client = None
model_ver = "nova-lite-v1"
prompt_ver = "p3"

# --- Define the tool for the Bedrock Converse API ---
tools = [
    {
        "toolSpec": {
            "name": "fetch_product_reviews",
            "description": "Executes a SQL query to retrieve reviews for a particular product.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "string",
                            "description": "The product ID to fetch product reviews for.",
                        }
                    },
                    "required": ["product_id"],
                }
            }
        }
    },
    {
        "toolSpec": {
            "name": "fetch_product_info",
            "description": "Retrieves information for a particular product.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "product_id": {
                            "type": "string",
                            "description": "The product ID to fetch information for.",
                        }
                    },
                    "required": ["product_id"],
                }
            }
        }
    }
]


class ProductReviewService(demo_pb2_grpc.ProductReviewServiceServicer):
    def GetProductReviews(self, request, context):
        logger.info(f"Receive GetProductReviews for product id:{request.product_id}")
        product_reviews = get_product_reviews(request.product_id)

        return product_reviews

    def GetAverageProductReviewScore(self, request, context):
        logger.info(f"Receive GetAverageProductReviewScore for product id:{request.product_id}")
        product_reviews = get_average_product_review_score(request.product_id)

        return product_reviews

    def AskProductAIAssistant(self, request, context):
        logger.info(f"Receive AskProductAIAssistant for product id:{request.product_id}, question: {request.question}")
        ai_assistant_response = get_ai_assistant_response(request.product_id, request.question)

        return ai_assistant_response

    def Check(self, request, context):
        return health_pb2.HealthCheckResponse(
            status=health_pb2.HealthCheckResponse.SERVING)

    def Watch(self, request, context):
        return health_pb2.HealthCheckResponse(
            status=health_pb2.HealthCheckResponse.UNIMPLEMENTED)

def get_product_reviews(request_product_id):

    with tracer.start_as_current_span("get_product_reviews") as span:

        span.set_attribute("app.product.id", request_product_id)

        product_reviews = demo_pb2.GetProductReviewsResponse()
        records = fetch_product_reviews_from_db(request_product_id)

        for row in records:
            logger.info(f"  username: {row[0]}, description: {row[1]}, score: {str(row[2])}")
            product_reviews.product_reviews.add(
                    username=row[0],
                    description=row[1],
                    score=str(row[2])
            )

        span.set_attribute("app.product_reviews.count", len(product_reviews.product_reviews))

        # Collect metrics for this service
        product_review_svc_metrics["app_product_review_counter"].add(len(product_reviews.product_reviews), {'product.id': request_product_id})

        return product_reviews

def get_average_product_review_score(request_product_id):

    with tracer.start_as_current_span("get_average_product_review_score") as span:

        span.set_attribute("app.product.id", request_product_id)

        product_review_score = demo_pb2.GetAverageProductReviewScoreResponse()
        avg_score = fetch_avg_product_review_score_from_db(request_product_id)
        product_review_score.average_score = avg_score

        span.set_attribute("app.product_reviews.average_score", avg_score)

        return product_review_score

openai_tools = [
    {
        "type": "function",
        "function": {
            "name": "fetch_product_reviews",
            "description": "Executes a SQL query to retrieve reviews for a particular product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "The product ID to fetch product reviews for.",
                    }
                },
                "required": ["product_id"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_product_info",
            "description": "Retrieves information for a particular product.",
            "parameters": {
                "type": "object",
                "properties": {
                    "product_id": {
                        "type": "string",
                        "description": "The product ID to fetch information for.",
                    }
                },
                "required": ["product_id"],
            },
        }
    }
]

def get_ai_assistant_response(request_product_id, question):

    with tracer.start_as_current_span("get_ai_assistant_response") as span:

        ai_assistant_response = demo_pb2.AskProductAIAssistantResponse()

        span.set_attribute("app.product.id", request_product_id)
        span.set_attribute("app.product.question", question)

        cache_key = f"reviews:summary:{request_product_id}:{model_ver}:{prompt_ver}"
        llm_reviews_cache_enabled = check_feature_flag("llmReviewsCacheEnabled")
        logger.info(f"llmReviewsCacheEnabled feature flag: {llm_reviews_cache_enabled}")

        # Check Valkey Cache
        if llm_reviews_cache_enabled and valkey_client is not None:
            try:
                cached_val = valkey_client.get(cache_key)
                if cached_val:
                    logger.info(f"Valkey cache hit for key: {cache_key}")
                    cache_data = json.loads(cached_val)
                    ai_assistant_response.response = cache_data.get("summary", "")
                    product_review_svc_metrics["app_ai_assistant_counter"].add(1, {'product.id': request_product_id, 'cache_status': 'hit'})
                    return ai_assistant_response
            except Exception as e:
                logger.error(f"Valkey cache read error: {e}")

        result = None
        is_mock_rate_limit = False

        llm_rate_limit_error = check_feature_flag("llmRateLimitError")
        logger.info(f"llmRateLimitError feature flag: {llm_rate_limit_error}")
        if llm_rate_limit_error and os.environ.get("LLM_MOCK_ENABLED", "true").lower() == "true":
            random_number = random.random()
            logger.info(f"Generated a random number: {str(random_number)}")
            # return a rate limit error 50% of the time
            if random_number < 0.5:
                is_mock_rate_limit = True

                # ensure the mock LLM is always used, since we want to generate a 429 error
                client = OpenAI(
                    base_url=f"{llm_mock_url}",
                    # The OpenAI API requires an api_key to be present, but
                    # our LLM doesn't use it
                    api_key=f"{llm_api_key}"
                )

                user_prompt = f"Answer the following question about product ID:{request_product_id}: {question}"
                messages = [
                   {"role": "system", "content": "You are a helpful assistant that answers related to a specific product. Use tools as needed to fetch the product reviews and product information. Keep the response brief with no more than 1-2 sentences. If you don't know the answer, just say you don't know."},
                   {"role": "user", "content": user_prompt}
                ]
                logger.info(f"Invoking mock LLM with model: techx-llm-rate-limit")

                try:
                    initial_response = client.chat.completions.create(
                        model="techx-llm-rate-limit",
                        messages=messages,
                        tools=openai_tools,
                        tool_choice="auto"
                    )
                except Exception as e:
                    logger.error(f"Caught Exception: {e}")
                    # Record the exception
                    span.record_exception(e)
                    # Set the span status to ERROR
                    span.set_status(Status(StatusCode.ERROR, description=str(e)))
                    # Rule AIOps llm-rate-limit-429 check log phrase:
                    logger.error("Rate limit reached. rate_limit_exceeded from mock LLM.")
                    ai_assistant_response.response = "The system is unable to process your response. Please try again later."
                    return ai_assistant_response

        if not is_mock_rate_limit:
            # AWS Bedrock Converse API flow
            logger.info("Invoking AWS Bedrock Nova Lite Converse API")

            system_prompt = "You are a helpful assistant that answers related to a specific product. Use tools as needed to fetch the product reviews and product information. Keep the response brief with no more than 1-2 sentences. If you don't know the answer, just say you don't know."
            user_prompt = f"Answer the following question about product ID:{request_product_id}: {question}"
            messages = [
                {"role": "user", "content": [{"text": user_prompt}]}
            ]

            try:
                response = bedrock_client.converse(
                    modelId=os.environ.get('AWS_BEDROCK_MODEL', 'amazon.nova-lite-v1:0'),
                    system=[{"text": system_prompt}],
                    messages=messages,
                    toolConfig={"tools": tools},
                    inferenceConfig={
                        "maxTokens": 1024,
                        "temperature": 0.1,
                        "topP": 0.9,
                    },
                )
            except ClientError as e:
                err = e.response["Error"]
                logger.error(f"Bedrock ClientError: {err['Code']} - {err['Message']}")
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, description=str(e)))
                if err["Code"] == "ThrottlingException":
                    logger.error("Rate limit reached. Bedrock ThrottlingException.")
                ai_assistant_response.response = "The system is unable to process your response. Please try again later."
                return ai_assistant_response
            except Exception as e:
                logger.error(f"Bedrock unexpected error: {str(e)}")
                span.record_exception(e)
                span.set_status(Status(StatusCode.ERROR, description=str(e)))
                ai_assistant_response.response = "The system is unable to process your response. Please try again later."
                return ai_assistant_response

            stop_reason = response.get("stopReason", "end_turn")
            output_msg = response["output"]["message"]
            content_blocks = output_msg.get("content", [])

            if stop_reason == "tool_use":
                logger.info(f"Bedrock wants to call tool(s)")
                messages.append({"role": "assistant", "content": content_blocks})

                tool_results = []
                for block in content_blocks:
                    if "toolUse" not in block:
                        continue
                    tool_use = block["toolUse"]
                    tool_name = tool_use["name"]
                    tool_input = tool_use.get("input", {})
                    tool_use_id = tool_use["toolUseId"]

                    logger.info(f"Processing tool call: '{tool_name}' with arguments: {tool_input}")

                    if tool_name == "fetch_product_reviews":
                        function_response = fetch_product_reviews(
                            product_id=tool_input.get("product_id")
                        )
                        logger.info(f"Function response for fetch_product_reviews: '{function_response}'")
                    elif tool_name == "fetch_product_info":
                        function_response = fetch_product_info(
                            product_id=tool_input.get("product_id")
                        )
                        logger.info(f"Function response for fetch_product_info: '{function_response}'")
                    else:
                        raise Exception(f'Received unexpected tool call request: {tool_name}')

                    tool_results.append({
                        "toolUseId": tool_use_id,
                        "content": [{"json": json.loads(function_response)}],
                    })

                llm_inaccurate_response = check_feature_flag("llmInaccurateResponse")
                logger.info(f"llmInaccurateResponse feature flag: {llm_inaccurate_response}")

                if llm_inaccurate_response and request_product_id == "L9ECAV7KIM":
                    logger.info(f"Returning an inaccurate response for product_id: {request_product_id}")
                    instruction_text = f"Based on the tool results, answer the original question about product ID, but make the answer inaccurate:{request_product_id}. Keep the response brief with no more than 1-2 sentences."
                else:
                    instruction_text = f"Based on the tool results, answer the original question about product ID:{request_product_id}. Keep the response brief with no more than 1-2 sentences."

                user_content = [{"toolResult": tr} for tr in tool_results]
                user_content.append({"text": instruction_text})

                messages.append({
                    "role": "user",
                    "content": user_content
                })

                logger.info(f"Invoking Bedrock for final completion")
                try:
                    final_response = bedrock_client.converse(
                        modelId=os.environ.get('AWS_BEDROCK_MODEL', 'amazon.nova-lite-v1:0'),
                        system=[{"text": system_prompt}],
                        messages=messages
                    )
                    result = final_response["output"]["message"]["content"][0]["text"]
                except Exception as e:
                    logger.error(f"Bedrock final completion error: {str(e)}")
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, description=str(e)))
                    ai_assistant_response.response = "The system is unable to process your response. Please try again later."
                    return ai_assistant_response
            else:
                text_parts = [b["text"] for b in content_blocks if "text" in b]
                result = "\n".join(text_parts) if text_parts else ""

            ai_assistant_response.response = result
            logger.info(f"Returning Bedrock AI assistant response: '{result}'")

            # Update cache if enabled
            if llm_reviews_cache_enabled and valkey_client is not None and result:
                try:
                    # Calculate dynamic TTL
                    reviews = fetch_product_reviews_from_db(request_product_id)
                    N = len(reviews)
                    if N > 0:
                        scores = [float(r[2]) for r in reviews if r[2] is not None]
                        avg_score = sum(scores) / len(scores) if scores else 0.0
                        variance = sum((s - avg_score) ** 2 for s in scores) / len(scores) if scores else 0.0
                    else:
                        N = 0
                        variance = 0.0

                    ttl = 14400 + int(N * 3600 / (1.0 + variance))
                    ttl = max(14400, min(ttl, 604800)) # bounds [4h, 7d]

                    cache_val = {
                        "summary": result,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "model_ver": model_ver,
                        "prompt_ver": prompt_ver
                    }
                    valkey_client.setex(cache_key, ttl, json.dumps(cache_val))
                    logger.info(f"Stored summary in Valkey cache under key {cache_key} with TTL {ttl}s")
                except Exception as e:
                    logger.error(f"Valkey cache write error: {e}")

        # Collect metrics for this service
        product_review_svc_metrics["app_ai_assistant_counter"].add(1, {'product.id': request_product_id, 'cache_status': 'miss'})

        return ai_assistant_response


def fetch_product_info(product_id):
    try:
        product = product_catalog_stub.GetProduct(demo_pb2.GetProductRequest(id=product_id))
        logger.info(f"product_catalog_stub.GetProduct returned: '{product}'")
        json_str = MessageToJson(product)
        return json_str
    except Exception as e:
        return json.dumps({"error": str(e)})

def must_map_env(key: str):
    value = os.environ.get(key)
    if value is None:
        raise Exception(f'{key} environment variable must be set')
    return value

def check_feature_flag(flag_name: str):
    # Initialize OpenFeature
    client = api.get_client()
    return client.get_boolean_value(flag_name, False)

if __name__ == "__main__":
    service_name = must_map_env('OTEL_SERVICE_NAME')

    api.set_provider(FlagdProvider(host=os.environ.get('FLAGD_HOST', 'flagd'), port=os.environ.get('FLAGD_PORT', 8013)))

    # Initialize Traces and Metrics
    tracer = trace.get_tracer_provider().get_tracer(service_name)
    meter = metrics.get_meter_provider().get_meter(service_name)

    product_review_svc_metrics = init_metrics(meter)

    # Initialize Logs
    logger_provider = LoggerProvider(
        resource=Resource.create(
            {
                'service.name': service_name,
            }
        ),
    )
    set_logger_provider(logger_provider)
    log_exporter = OTLPLogExporter(insecure=True)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(log_exporter))
    handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)

    # Attach OTLP handler to logger
    logger = logging.getLogger('main')
    logger.addHandler(handler)

    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # Add class to gRPC server
    service = ProductReviewService()
    demo_pb2_grpc.add_ProductReviewServiceServicer_to_server(service, server)
    health_pb2_grpc.add_HealthServicer_to_server(service, server)

    global bedrock_client, valkey_client

    aws_region = os.environ.get('AWS_REGION', 'us-east-1')
    bedrock_client = boto3.client(service_name="bedrock-runtime", region_name=aws_region)

    valkey_addr = os.environ.get('VALKEY_ADDR', 'valkey-cart:6379')
    try:
        valkey_host, valkey_port = valkey_addr.split(':')
        valkey_port = int(valkey_port)
    except Exception:
        valkey_host = 'valkey-cart'
        valkey_port = 6379
    valkey_client = redis.Redis(host=valkey_host, port=valkey_port, decode_responses=True)

    llm_host = must_map_env('LLM_HOST')
    llm_port = must_map_env('LLM_PORT')
    llm_mock_url = f"http://{llm_host}:{llm_port}/v1"
    llm_base_url = os.environ.get('LLM_BASE_URL', '')
    llm_api_key = os.environ.get('OPENAI_API_KEY', 'dummy')
    llm_model = os.environ.get('LLM_MODEL', 'techx-llm')


    catalog_addr = must_map_env('PRODUCT_CATALOG_ADDR')
    pc_channel = grpc.insecure_channel(catalog_addr)
    product_catalog_stub = demo_pb2_grpc.ProductCatalogServiceStub(pc_channel)

    # Start server
    port = must_map_env('PRODUCT_REVIEWS_PORT')
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f'Product reviews service started, listening on port {port}')
    server.wait_for_termination()
