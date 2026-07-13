#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Python
import os
import simplejson as json

# Postgres
import psycopg2

def must_map_env(key: str):
    value = os.environ.get(key)
    if value is None:
        raise Exception(f'{key} environment variable must be set')
    return value

# Retrieve Postgres environment variables
db_connection_str = must_map_env('DB_CONNECTION_STRING')

def fetch_product_reviews(product_id):
    try:
        return json.dumps(fetch_product_reviews_from_db(product_id), use_decimal=True)
    except Exception as e:
        return json.dumps({"error": str(e)})

def fetch_product_reviews_from_db(request_product_id):

    connection = None

    try:
        with psycopg2.connect(db_connection_str) as connection:

            with connection.cursor() as cursor:
                # Define the SQL query
                query = "SELECT username, description, score FROM reviews.productreviews WHERE product_id= %s"

                # Execute the query
                cursor.execute(query, (request_product_id, ))

                # Fetch all the rows from the query result
                records = cursor.fetchall()
                return records

    except Exception as e:
        raise e
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception as e:
                pass

def fetch_reviews_fingerprint(request_product_id):
    """Content fingerprint cua tap review 1 san pham — cho content-addressed cache key.

    Co che chuan the gioi (Rails cache_key / HTTP ETag): key = ham cua STATE object.
    Review doi (them/sua/xoa) -> fingerprint doi -> cache key doi -> MISS tu nhien,
    khong bao gio serve summary cu. Khong dynamic-TTL doan, khong invalidate thu cong.

    1 aggregate query, index san tren product_id, ~5 dong/san pham -> re hon LLM call ~1000x.
    - COUNT + MAX(id): bat them/xoa review (id la IDENTITY PK auto-increment).
    - md5(content): bat SUA review (description/score doi ma count/id khong doi).
    """
    connection = None
    try:
        with psycopg2.connect(db_connection_str) as connection:
            with connection.cursor() as cursor:
                query = (
                    "SELECT COUNT(*), COALESCE(MAX(id), 0), "
                    "COALESCE(MD5(STRING_AGG(description || '|' || score::text, ',' ORDER BY id)), '') "
                    "FROM reviews.productreviews WHERE product_id = %s"
                )
                cursor.execute(query, (request_product_id,))
                count, max_id, content_md5 = cursor.fetchone()
                import hashlib
                raw = f"{count}:{max_id}:{content_md5}"
                return hashlib.md5(raw.encode()).hexdigest()[:12]
    except Exception as e:
        raise e
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass

def fetch_avg_product_review_score_from_db(request_product_id):

    connection = None

    try:
        with psycopg2.connect(db_connection_str) as connection:

            with connection.cursor() as cursor:
                # Define the SQL query
                query = "SELECT AVG(score) FROM reviews.productreviews WHERE product_id= %s"

                # Execute the query
                cursor.execute(query, (request_product_id, ))

                # Fetch all the rows from the query result
                records = cursor.fetchall()

                # Extract the average score
                if records:
                    # records will be a list like [(average_score,)]
                    average_score = records[0][0]
                else:
                    # Handle the case where no records are returned (e.g., no reviews for the product)
                    average_score = None

                # return the score as a string rounded to 1 decimal place
                return f"{average_score:.1f}"

    except Exception as e:
        raise e
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception as e:
                pass
