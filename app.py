import json
import boto3
import psycopg2
import datetime
import hashlib

def mask_value(value):
    # Use a hash function to create a consistent token
    hashed_value = hashlib.sha256(value.encode()).hexdigest()
    return "token_" + hashed_value[:8]  # Use only the first 8 characters for visibility

def process_record(record):
    # Your logic to flatten and mask the JSON record
    # print(record)
    
    if 'user_id' not in record.keys():
        print(record)
        return None
    
    flattened_record = {
        'user_id': record['user_id'],
        'device_type': record['device_type'],
        'masked_ip': mask_value(record['ip']),
        'masked_device_id': mask_value(record['device_id']),
        'locale': record['locale'],
        'app_version': int(record['app_version'].split(".")[0]),
        'create_date': datetime.date.today()
    }
    return flattened_record

def main():
    sqs = boto3.client('sqs', endpoint_url='http://localhost:4566/000000000000/login-queue')
    queue_url = 'http://localhost:4566/000000000000/login-queue'
    
    conn = psycopg2.connect(
        host='localhost',
        port=5432,
        user='postgres',
        password='postgres',
        database='postgres'
    )
    cursor = conn.cursor()
    count  = 0
    
    while True:
        # Receive message from SQS
        
        response = sqs.receive_message(
            QueueUrl=queue_url,
            AttributeNames=['All'],
            MaxNumberOfMessages=1,
            MessageAttributeNames=['All'],
            VisibilityTimeout=0,
            WaitTimeSeconds=0
        )
        
        appx_messages = int(response['Messages'][0]['Attributes']['ApproximateReceiveCount'])
        if appx_messages == 0:
            print("Done processing all the messages")
            break
        
        count = count + 1
        if 'Messages' in response:
            print("Processing message # %s", count)
            message = response['Messages'][0]
            body = json.loads(message['Body'])

            # Process and mask the record
            processed_record = process_record(body)

            if processed_record == None:
                continue
            
            # Insert into Postgres
            cursor.execute("""
                INSERT INTO user_logins 
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                processed_record['user_id'],
                processed_record['device_type'],
                processed_record['masked_ip'],
                processed_record['masked_device_id'],
                processed_record['locale'],
                processed_record['app_version'],
                processed_record['create_date']
            ))
            conn.commit()

            # Delete received message from SQS
            sqs.delete_message(
                QueueUrl=queue_url,
                ReceiptHandle=message['ReceiptHandle']
            )

    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()
