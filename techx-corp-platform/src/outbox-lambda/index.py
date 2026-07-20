import os
import json
import boto3
from kafka import KafkaProducer

# Define in a global scope (warm start)
secrets_client = boto3.client('secretsmanager')

MSK_CREDENTIALS_SECRET_ARN = os.environ['MSK_CREDENTIALS_SECRET_ARN']
MSK_ENDPOINT_SECRET_ARN = os.environ['MSK_ENDPOINT_SECRET_ARN']
KAFKA_TOPIC = os.environ.get('KAFKA_TOPIC', 'orders')

producer = None

# Get secret from AWS Secrets Manager 
def get_secret(secret_arn):
	response = secrets_client.get_secret_value(SecretId=secret_arn)
	return json.loads(response['SecretString'])

# Initialize Kafka Producer
def init_producer():
	global producer 
	if producer is not None:
		return 
	
	# Get MSK credentials & endpoint 
	msk_credentials = get_secret(MSK_CREDENTIALS_SECRET_ARN)
	msk_endpoint = get_secret(MSK_ENDPOINT_SECRET_ARN)
	
	brokers = msk_endpoint['broker_sasl_scram'].split(',')
	
	producer = KafkaProducer(
		bootstrap_servers=brokers,
		security_protocol='SASL_SSL',
		sasl_mechanism='SCRAM-SHA-512',
		sasl_plain_username=msk_credentials['username'],
		sasl_plain_password=msk_credentials['password'],
		key_serializer=lambda k: k.encode('utf-8'),
		value_serializer=lambda v: v.encode('utf-8')
	)
	
def handler(event, context):
	"""
	Purpose: Main Entrypoint 
	"""
	init_producer()
 
	# Batch processing
	for record in event.get('Records', []):
		if record['eventName'] in ['INSERT', 'MODIFY']:
			new_image = record['dynamodb']['NewImage']
   
			order_id = new_image.get('order_id', {}).get('S')
			order_data_str = new_image.get('order_data', {}).get('S')
   
			if not order_data_str:
				print(f"Skipping order {order_id}: No 'order_data' found in DB record.")
				continue
   
			producer.send(KAFKA_TOPIC, key=order_id, value=order_data_str)
			print(f"Successfully relayed order {order_id} to MSK topic: {KAFKA_TOPIC}")
		
	producer.flush()
 
	return {
		'statusCode': 200,
		'body': json.dumps('Messages processed successfully')
	}
