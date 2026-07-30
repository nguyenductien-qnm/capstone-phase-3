#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

def init_metrics(meter):

    # Product reviews counter
    app_product_review_counter = meter.create_counter(
        'app_product_review_counter', unit='reviews', description="Counts the total number of returned product reviews"
    )

    # AI Assistant counter
    app_ai_assistant_counter = meter.create_counter(
        'app_ai_assistant_counter', unit='summaries', description="Counts the total number of AI Assistant requests"
    )

    # Bedrock token counters
    bedrock_input_tokens_total = meter.create_counter(
        'bedrock_input_tokens_total', unit='tokens', description="Cumulative count of input tokens sent to Bedrock API"
    )

    bedrock_output_tokens_total = meter.create_counter(
        'bedrock_output_tokens_total', unit='tokens', description="Cumulative count of output tokens received from Bedrock API"
    )

    bedrock_cost_usd_total = meter.create_counter(
        'bedrock_cost_usd_total', unit='USD', description="Estimated cumulative cost of Bedrock API calls (input: $0.30/1M, output: $0.60/1M)"
    )

    product_review_svc_metrics = {
        "app_product_review_counter": app_product_review_counter,
        "app_ai_assistant_counter": app_ai_assistant_counter,
        "bedrock_input_tokens_total": bedrock_input_tokens_total,
        "bedrock_output_tokens_total": bedrock_output_tokens_total,
        "bedrock_cost_usd_total": bedrock_cost_usd_total,
    }

    return product_review_svc_metrics
