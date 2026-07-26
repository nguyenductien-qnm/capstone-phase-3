#!/usr/bin/env python3
import os
import json
import boto3
import psycopg2

def main():
    # 1. Connect to PostgreSQL
    db_conn_str = os.environ.get(
        "DB_CONNECTION_STRING", 
        "postgres://otelu:otelp@localhost:5432/otel"
    )
    
    print(f"Connecting to database...")
    conn = psycopg2.connect(db_conn_str)
    conn.autocommit = True
    cursor = conn.cursor()
    
    # 2. Fetch all products
    print("Fetching products from catalog.products...")
    cursor.execute("SELECT id, name, description, categories FROM catalog.products")
    products = cursor.fetchall()
    
    if not products:
        print("No products found.")
        return
        
    print(f"Found {len(products)} products.")
    
    # 3. Setup AWS Bedrock client
    print("Setting up Bedrock client...")
    bedrock = boto3.client(
        service_name='bedrock-runtime',
        region_name=os.environ.get('AWS_REGION', 'us-east-1')
    )
    
    # 4. Generate embeddings and update
    for product in products:
        prod_id, name, description, categories = product
        
        text = f"{name}. {description}. Categories: {categories}"
        print(f"Generating embedding for product: {prod_id}")
        
        body = json.dumps({
            "inputText": text,
            "dimensions": 1024,
            "normalize": True
        })
        
        response = bedrock.invoke_model(
            body=body,
            modelId='amazon.titan-embed-text-v2:0',
            accept='application/json',
            contentType='application/json'
        )
        
        response_body = json.loads(response.get('body').read())
        embedding = response_body.get('embedding')
        
        if not embedding:
            print(f"Failed to get embedding for {prod_id}")
            continue
            
        print(f"Updating database for {prod_id}...")
        cursor.execute(
            "UPDATE catalog.products SET embedding = %s WHERE id = %s",
            (embedding, prod_id)
        )
        
    print("All products successfully embedded.")
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
