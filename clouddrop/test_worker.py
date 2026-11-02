import json
import boto3
from config import settings
from worker import process_job

sqs = boto3.client('sqs', region_name=settings.region)
resp = sqs.receive_message(QueueUrl=settings.sqs_url, MaxNumberOfMessages=1, WaitTimeSeconds=2)
msgs = resp.get('Messages', [])
print(f'Received: {len(msgs)} messages')
if msgs:
    body = json.loads(msgs[0]['Body'])
    print(f'Processing: {body}')
    process_job(
        job_id=body['job_id'],
        operation=body.get('operation', 'compress'),
        input_keys=body.get('input_keys', []),
        filename=body.get('filename', 'document.pdf'),
        original_size=body.get('original_size', 0),
        options=body.get('options', {}),
        email=body.get('email', ''),
    )
    sqs.delete_message(QueueUrl=settings.sqs_url, ReceiptHandle=msgs[0]['ReceiptHandle'])
    print('Completed process_job!')
