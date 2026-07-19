import psycopg2
import sys
import time
import traceback

conn_string = "postgresql://db_admin:cL3xc5VLcxkM4hU2@ecommerce-dev-postgres.c2x20s086fm5.us-east-1.rds.amazonaws.com:5432/ecommerce_db?sslmode=require"

def main():
    try:
        print("Connecting to database...")
        conn = psycopg2.connect(conn_string)
        conn.autocommit = True
        cursor = conn.cursor()

        # 1. Check if test rows exist
        cursor.execute("SELECT COUNT(*) FROM catalog.products WHERE id LIKE 'TEST_PROD_%%';")
        res = cursor.fetchone()
        print(f"Fetchone result: {res}")
        count = res[0]
        print(f"Current test rows count: {count}")

        if count < 100000:
            print("Inserting 100,000 test rows...")
            cursor.execute("""
                INSERT INTO catalog.products (id, name, description, picture, price_currency_code, price_units, price_nanos, categories)
                SELECT
                    'TEST_PROD_' || i,
                    'Sản phẩm thử nghiệm hiệu năng số ' || i,
                    'Mô tả chi tiết sản phẩm phục vụ cho bài test tải hiệu năng của Mandate 09.',
                    'StarsenseExplorer.jpg',
                    'USD',
                    100 + (i % 500),
                    950000000,
                    'telescopes,accessories'
                FROM generate_series(1, 100000) s(i)
                ON CONFLICT (id) DO NOTHING;
            """)
            print("Insert completed.")

        # 2. Reset image_url to NULL
        print("Resetting image_url to NULL for test rows...")
        cursor.execute("UPDATE catalog.products SET image_url = NULL WHERE id LIKE 'TEST_PROD_%%';")
        print("Reset completed.")

        # 3. Start backfill migration
        chunk_size = 300
        sleep_sec = 0.1
        processed = 0

        print(f"Starting backfill migration: chunk_size={chunk_size}, sleep_sec={sleep_sec}...")
        start_time = time.time()

        while True:
            cursor.execute("""
                WITH batch AS (
                    SELECT id
                    FROM catalog.products
                    WHERE image_url IS NULL AND id LIKE 'TEST_PROD_%%'
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                )
                UPDATE catalog.products p
                SET image_url = p.picture
                FROM batch
                WHERE p.id = batch.id;
            """, (chunk_size,))

            r_count = cursor.rowcount
            processed += r_count

            if r_count == 0:
                break

            print(f"Processed {processed} rows...", end="\r")
            sys.stdout.flush()
            time.sleep(sleep_sec)

        end_time = time.time()
        duration = end_time - start_time
        print(f"\nBackfill completed!")
        print(f"Total processed: {processed} rows")
        print(f"Duration: {duration:.2f} seconds")

        cursor.close()
        conn.close()
    except Exception as e:
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
