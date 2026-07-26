#!/usr/bin/env python3
import os
import json
import logging
import psycopg2
import boto3
from botocore.credentials import RefreshableCredentials
from botocore.session import get_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("embed_products")


def create_bedrock_client(region_name: str):
    """Creates a Bedrock runtime client supporting cross-account IRSA assume-role."""
    role_arn = os.environ.get("BEDROCK_AWS_ROLE_ARN")
    if role_arn and role_arn != "<your-role-arn>":
        session_name = os.environ.get("BEDROCK_AWS_ROLE_SESSION_NAME", "embed-products-bedrock")
        assume_role_kwargs = {
            "RoleArn": role_arn,
            "RoleSessionName": session_name,
        }
        external_id = os.environ.get("BEDROCK_AWS_EXTERNAL_ID")
        if external_id:
            assume_role_kwargs["ExternalId"] = external_id

        sts = boto3.client("sts", region_name=region_name)

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
        logger.info("Using assumed-role credentials for Bedrock: %s", role_arn)
        return session.client("bedrock-runtime", region_name=region_name)

    logger.info("Using default AWS provider chain for Bedrock runtime")
    return boto3.client("bedrock-runtime", region_name=region_name)


func_get_db_conn = None


def connect_db():
    conn_str = os.environ.get("DB_CONNECTION_STRING") or os.environ.get("DATABASE_URL")
    if conn_str:
        logger.info("Connecting to PostgreSQL via connection string...")
        conn = psycopg2.connect(conn_str)
    else:
        host = os.environ.get("POSTGRES_HOST", "localhost")
        port = os.environ.get("POSTGRES_PORT", "5432")
        user = os.environ.get("POSTGRES_USER", "otelu")
        password = os.environ.get("POSTGRES_PASSWORD", "otelp")
        dbname = os.environ.get("POSTGRES_DB", "otel")
        logger.info("Connecting to PostgreSQL at %s:%s/%s...", host, port, dbname)
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=dbname
        )
    conn.autocommit = True
    return conn


def main():
    region = os.environ.get("AWS_REGION", "us-east-1")
    bedrock = create_bedrock_client(region)
    conn = connect_db()
    cursor = conn.cursor()

    # Ensure pgvector extension and table exist
    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS catalog.product_embeddings_v2 (
            product_id VARCHAR(255) PRIMARY KEY,
            embedding vector(1024)
        );
    """)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS product_embeddings_v2_hnsw_idx 
        ON catalog.product_embeddings_v2 USING hnsw (embedding vector_cosine_ops);
    """)

    logger.info("Fetching products from catalog.products...")
    cursor.execute("SELECT id, name, description, categories FROM catalog.products")
    products = cursor.fetchall()

    if not products:
        logger.warning("No products found in catalog.products.")
        return

    logger.info("Found %d products. Generating embeddings...", len(products))

    success_count = 0
    for product in products:
        prod_id, name, description, categories = product
        text = f"{name}. {description}. Categories: {categories}"

        body = json.dumps({
            "inputText": text,
            "dimensions": 1024,
            "normalize": True
        })

        try:
            response = bedrock.invoke_model(
                body=body,
                modelId="amazon.titan-embed-text-v2:0",
                accept="application/json",
                contentType="application/json"
            )
            response_body = json.loads(response.get("body").read())
            embedding = response_body.get("embedding")
        except Exception as err:
            logger.error("Failed to generate embedding for product %s: %s", prod_id, err)
            continue

        if not embedding:
            logger.error("Empty embedding returned for product %s", prod_id)
            continue

        # Format float list as pgvector string representation: '[0.1, -0.2, ...]'
        vec_str = str(embedding)

        cursor.execute(
            """
            INSERT INTO catalog.product_embeddings_v2 (product_id, embedding)
            VALUES (%s, %s)
            ON CONFLICT (product_id) DO UPDATE SET embedding = EXCLUDED.embedding;
            """,
            (prod_id, vec_str)
        )
        success_count += 1
        logger.info("Successfully upserted embedding for product %s (%d/%d)", prod_id, success_count, len(products))

    logger.info("Done! Embedded %d/%d products successfully into catalog.product_embeddings_v2.", success_count, len(products))
    cursor.close()
    conn.close()


if __name__ == "__main__":
    main()

