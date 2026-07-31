#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


# Python
import os
import random
import logging
import threading
from concurrent import futures

logger = logging.getLogger('main')

# Pip
import grpc
import psycopg2
import psycopg2.pool
from pgvector.psycopg2 import register_vector
from opentelemetry import trace, metrics
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
    OTLPLogExporter,
)
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider

from openfeature.contrib.hook.opentelemetry import TracingHook

# Local
import logging
import demo_pb2
import demo_pb2_grpc
from grpc_health.v1 import health_pb2
from grpc_health.v1 import health_pb2_grpc

from metrics import (
    init_metrics
)

cached_ids = []
first_run = True

class RecommendationService(demo_pb2_grpc.RecommendationServiceServicer):
    """Recommendation Service.

    Provides AI-driven product recommendations based on product embeddings stored in PostgreSQL (pgvector).
    Includes a feature flag (aiRecommendationsEnabled) to fallback to random recommendations if disabled or if
    the database is unavailable.
    """
    def ListRecommendations(self, request, context):
        prod_list = get_product_list(request.product_ids)
        span = trace.get_current_span()
        span.set_attribute("app.products_recommended.count", len(prod_list))
        logger.info(f"Receive ListRecommendations for product ids:{prod_list}")

        # build and return response
        response = demo_pb2.ListRecommendationsResponse()
        response.product_ids.extend(prod_list)

        # Collect metrics for this service
        rec_svc_metrics["app_recommendations_counter"].add(len(prod_list), {'recommendation.type': 'catalog'})

        return response

    def Check(self, request, context):
        return health_pb2.HealthCheckResponse(
            status=health_pb2.HealthCheckResponse.SERVING)

    def Watch(self, request, context):
        return health_pb2.HealthCheckResponse(
            status=health_pb2.HealthCheckResponse.UNIMPLEMENTED)


def get_product_list(request_product_ids):
    with tracer.start_as_current_span("get_product_list") as span:
        max_responses = 5

        # Formulate the list of characters to list of strings
        request_product_ids_str = ''.join(request_product_ids)
        request_product_ids_list = request_product_ids_str.split(',')

        if check_feature_flag("aiRecommendationsEnabled"):
            span.set_attribute("app.recommendation.type", "ai-embedding")
            return _get_ai_recommendations(request_product_ids_list, max_responses)
        else:
            span.set_attribute("app.recommendation.type", "random-fallback")
            return _get_random_recommendations(request_product_ids_list, max_responses)


db_pool = None
_db_pool_lock = threading.Lock()

# Cùng lý do như product-reviews/database.py: app đi qua RDS Proxy
# (MaxConnectionsPercent 100) và instance là db.t4g.micro (~100 max_connections),
# nên pool phía client giữ nhỏ thay vì 10 mỗi pod.
_POOL_MAX = int(os.environ.get('DB_POOL_MAX', '3'))


def get_db_pool():
    global db_pool
    if db_pool is None:
        # Lock + double-check: server chạy ThreadPoolExecutor(max_workers=10); không
        # khoá thì hai thread cùng dựng pool, một pool bị bỏ rơi kèm connection của nó.
        with _db_pool_lock:
            if db_pool is None:
                db_connection_str = os.environ.get('DB_CONNECTION_STRING')
                if db_connection_str:
                    # ThreadedConnectionPool: SimpleConnectionPool không thread-safe.
                    db_pool = psycopg2.pool.ThreadedConnectionPool(1, _POOL_MAX, db_connection_str)
    return db_pool

def _get_ai_recommendations(input_product_ids, max_results=5):
    """Retrieve AI-based recommendations using pgvector.

    Computes the average embedding vector of seed products, queries PostgreSQL using pgvector cosine distance,
    and returns the top 5 similar products. Fallbacks to random selection if any database error occurs.
    """
    with tracer.start_as_current_span("recommendation.ai_inference") as span:
        pool = get_db_pool()
        if not pool:
            logger.warning("DB_CONNECTION_STRING not set, falling back to random recommendations")
            return _get_random_recommendations(input_product_ids, max_results)
            
        connection = None
        broken = False
        try:
            connection = pool.getconn()
            try:
                register_vector(connection)
                with connection.cursor() as cursor:
                    placeholders = ','.join(['%s'] * len(input_product_ids))
                    cursor.execute(f"""
                        SELECT AVG(embedding) as avg_embedding
                        FROM catalog.product_embeddings_v2
                        WHERE product_id IN ({placeholders}) AND embedding IS NOT NULL
                    """, input_product_ids)
                    
                    avg_embedding = cursor.fetchone()[0]
                    if avg_embedding is None:
                        return _get_random_recommendations(input_product_ids, max_results)
                    
                    # pgvector returns numpy.float32 values; stringify plain floats so
                    # PostgreSQL receives "[0.1, ...]", not "[np.float32(0.1), ...]".
                    embedding_str = str([float(value) for value in avg_embedding])
                    cursor.execute("""
                        SELECT product_id as id
                        FROM catalog.product_embeddings_v2
                        WHERE product_id != ALL(%s) AND embedding IS NOT NULL
                        ORDER BY embedding <=> %s::vector
                        LIMIT %s
                    """, (input_product_ids, embedding_str, max_results))
                    
                    results = [row[0] for row in cursor.fetchall()]
                    span.set_attribute("app.ai_recommendations.count", len(results))
                    # Fallback to random if no results
                    if not results:
                        return _get_random_recommendations(input_product_ids, max_results)
                    return results
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                # Đánh dấu TRƯỚC khi finally chạy, nếu không thì `broken` vẫn False
                # lúc trả connection về pool.
                broken = True
                raise
            finally:
                # close=broken: connection chết vì RDS failover mà trả nguyên vẹn về
                # pool thì lần sau bốc trúng lại chính nó.
                pool.putconn(connection, close=broken)
        except Exception as e:
            logger.error(f"Error in AI recommendations: {e}")
            return _get_random_recommendations(input_product_ids, max_results)

def _get_random_recommendations(request_product_ids, max_responses=5):
    global first_run
    global cached_ids
    span = trace.get_current_span()
    # Feature flag scenario - Cache Leak
    if check_feature_flag("recommendationCacheFailure"):
        span.set_attribute("app.recommendation.cache_enabled", True)
        if random.random() < 0.5 or first_run:
            first_run = False
            span.set_attribute("app.cache_hit", False)
            logger.info("get_product_list: cache miss")
            cat_response = product_catalog_stub.GetProduct(demo_pb2.Empty())
            response_ids = [x.id for x in cat_response.products]
            cached_ids = cached_ids + response_ids
            cached_ids = cached_ids + cached_ids[:len(cached_ids) // 4]
            product_ids = cached_ids
        else:
            span.set_attribute("app.cache_hit", True)
            logger.info("get_product_list: cache hit")
            product_ids = cached_ids
    else:
        span.set_attribute("app.recommendation.cache_enabled", False)
        cat_response = product_catalog_stub.ListProducts(demo_pb2.Empty())
        product_ids = [x.id for x in cat_response.products]

    span.set_attribute("app.products.count", len(product_ids))

    # Create a filtered list of products excluding the products received as input
    filtered_products = list(set(product_ids) - set(request_product_ids))
    num_products = len(filtered_products)
    span.set_attribute("app.filtered_products.count", num_products)
    num_return = min(max_responses, num_products)

    # Sample list of indicies to return
    indices = random.sample(range(num_products), num_return)
    # Fetch product ids from indices
    prod_list = [filtered_products[i] for i in indices]

    span.set_attribute("app.filtered_products.list", prod_list)

    return prod_list


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
    api.add_hooks([TracingHook()])

    # Initialize Traces and Metrics
    tracer = trace.get_tracer_provider().get_tracer(service_name)
    meter = metrics.get_meter_provider().get_meter(service_name)
    rec_svc_metrics = init_metrics(meter)

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

    catalog_addr = must_map_env('PRODUCT_CATALOG_ADDR')
    pc_channel = grpc.insecure_channel(catalog_addr)
    product_catalog_stub = demo_pb2_grpc.ProductCatalogServiceStub(pc_channel)

    # Create gRPC server
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    # Add class to gRPC server
    service = RecommendationService()
    demo_pb2_grpc.add_RecommendationServiceServicer_to_server(service, server)
    health_pb2_grpc.add_HealthServicer_to_server(service, server)

    # Start server
    port = must_map_env('RECOMMENDATION_PORT')
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f'Recommendation service started, listening on port {port}')
    server.wait_for_termination()
