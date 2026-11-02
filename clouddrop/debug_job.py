import sys
import logging
logging.basicConfig(level=logging.DEBUG)

from database import get_conn
from worker import process_job

conn = get_conn()
cur = conn.cursor()
cur.execute("SELECT * FROM jobs WHERE job_id='72fefafc-7270-4da4-96ee-c88f1bd315d5'")
row = cur.fetchone()
print("Job row in DB:", row)
cur.close()
conn.close()

if row:
    print("Calling process_job directly...")
    import json
    opts = json.loads(row.get('options') or '{}')
    # Let's find input keys
    import boto3
    from config import settings
    s3 = boto3.client('s3', region_name=settings.region)
    resp = s3.list_objects_v2(Bucket=settings.s3_bucket, Prefix='uploads/72fefafc-7270-4da4-96ee-c88f1bd315d5/')
    keys = [item['Key'] for item in resp.get('Contents', [])]
    print("Found keys in S3:", keys)
    process_job(
        job_id=row['job_id'],
        operation=row['operation'],
        input_keys=keys,
        filename=row['filename'],
        original_size=row['original_size'],
        options=opts,
        email=''
    )
    print("process_job returned!")
