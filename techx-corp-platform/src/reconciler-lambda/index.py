import os
import json 
import boto3 
import time
from datetime import datetime 
import grpc 
import requests
from google.protobuf.json_format import Parse

# These will be generated in your CI/CD pipeline
import demo_pb2
import demo_pb2_grpc

DYNAMODB_TABLE_NAME = os.environ.get('DYNAMODB_TABLE_NAME')
PAYMENT_SVC_ADDR = os.environ.get('PAYMENT_SVC_ADDR', 'payment:50051')
SHIPPING_SVC_ADDR = os.environ.get('SHIPPING_SVC_ADDR', 'shipping:8080')

dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(DYNAMODB_TABLE_NAME)

def handler(event, context):
    print("Reconciler Lambda waking up...")
    now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Try to query using GSI, fallback to Scan if index doesn't exist
    try:
        response = table.query(
            IndexName='gsi_reconcile_due',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('reconcile_pk').eq('PENDING') & boto3.dynamodb.conditions.Key('reconcile_at').lte(now_str) # <=
        )
        stuck_orders = response.get('Items', [])
    except Exception as e:
        print(f"Failed to query index, falling back to scan: {e}")
        response = table.scan(
            FilterExpression=boto3.dynamodb.conditions.Attr('reconcile_pk').eq('PENDING') & boto3.dynamodb.conditions.Attr('reconcile_at').lte(now_str)
        )
        stuck_orders = response.get('Items', [])

    for order in stuck_orders:
        order_id = order['order_id']
        status = order['order_status']
        print(f"Reconciling order {order_id} at status {status}")

        retry_payload_str = order.get('retry_payload')
        order_data_str = order.get('order_data')
        
        if not retry_payload_str or not order_data_str:
            print(f"Skipping {order_id}: Missing payloads")
            continue

        req_payload = json.loads(retry_payload_str)
        order_result = json.loads(order_data_str)

        try:
            if status in ["PROCESSING", "PENDING_PAYMENT"]:
                # 1. PROCESS PAYMENT
                total_amount = calculate_total(order_result)
                print(f"Charging ${total_amount['units']}.{total_amount['nanos']} for order {order_id}")
                
                charge_card(req_payload['credit_card'], total_amount)
                
                # Payment success! Update state and move to shipping
                status = "PENDING_SHIPPING"
                table.update_item(
                    Key={'order_id': order_id},
                    UpdateExpression="SET order_status = :s, payment_status = :ps",
                    ExpressionAttributeValues={':s': status, ':ps': 'SUCCESS'}
                )

            if status == "PENDING_SHIPPING":
                # 2. PROCESS SHIPPING
                print(f"Shipping order {order_id}")
                tracking_id = ship_order(req_payload['address'], order_result['items'])
                
                # Update final order_result with tracking ID
                order_result['shipping_tracking_id'] = tracking_id
                
                # Shipping success! Mark as COMPLETED. 
                # Setting reconcile_pk to DONE removes it from the lambda's queue!
                table.update_item(
                    Key={'order_id': order_id},
                    UpdateExpression="SET order_status = :s, shipping_status = :ss, reconcile_pk = :rpk, order_data = :od",
                    ExpressionAttributeValues={
                        ':s': 'COMPLETED',
                        ':ss': 'SUCCESS',
                        ':rpk': 'DONE',
                        ':od': json.dumps(order_result)
                    }
                )
                print(f"Order {order_id} successfully reconciled to COMPLETED!")
                
        except Exception as e:
            print(f"Failed to reconcile order {order_id}: {e}")
            # Exponential backoff/retry logic: push the reconcile_at 10 minutes into the future
            next_retry = datetime.fromtimestamp(time.time() + 600).strftime("%Y-%m-%dT%H:%M:%SZ")
            table.update_item(
                Key={'order_id': order_id},
                UpdateExpression="SET reconcile_at = :ra",
                ExpressionAttributeValues={':ra': next_retry}
            )

def calculate_total(order_result):
    units = order_result.get('shipping_cost', {}).get('units', 0)
    nanos = order_result.get('shipping_cost', {}).get('nanos', 0)
    currency = order_result.get('shipping_cost', {}).get('currency_code', 'USD')
    
    for item in order_result.get('items', []):
        qty = item.get('item', {}).get('quantity', 0)
        cost_units = item.get('cost', {}).get('units', 0)
        cost_nanos = item.get('cost', {}).get('nanos', 0)
        
        units += cost_units * qty
        nanos += cost_nanos * qty
        
        if nanos >= 1000000000:
            units += nanos // 1000000000
            nanos = nanos % 1000000000
            
    return {'currency_code': currency, 'units': units, 'nanos': nanos}

def charge_card(credit_card_dict, amount_dict):
    channel = grpc.insecure_channel(PAYMENT_SVC_ADDR)
    stub = demo_pb2_grpc.PaymentServiceStub(channel)
    
    request = demo_pb2.ChargeRequest()
    Parse(json.dumps({'amount': amount_dict, 'credit_card': credit_card_dict}), request)
    
    # This throws an exception if it fails, which is caught by the try/except block above
    stub.Charge(request)

def ship_order(address_dict, items_list):
    # The checkout service called /ship-order using HTTP REST (not gRPC!)
    # We must do the same here!
    payload = {
        "address": address_dict,
        "items": []
    }
    # checkout passes cartItems to shipping, so we extract `item` from `OrderItem`
    for i in items_list:
        payload["items"].append(i["item"])
        
    url = f"{SHIPPING_SVC_ADDR}/ship-order"
    if not url.startswith("http"):
        url = "http://" + url
        
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status() # Throws exception if 500 error
    
    return response.json().get('tracking_id', 'UNKNOWN_TRACKING')