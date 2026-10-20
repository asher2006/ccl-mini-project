import boto3
import json
import os

def get_param(name: str, decrypt: bool = False) -> str:
    ssm = boto3.client("ssm", region_name="us-east-1")
    resp = ssm.get_parameter(Name=name, WithDecryption=decrypt)
    return resp["Parameter"]["Value"]

class Settings:
    region: str = "us-east-1"
    s3_bucket: str = ""
    sqs_url: str = ""
    sns_arn: str = ""
    proxy_url: str = ""
    db_host: str = ""
    db_port: int = 5432
    db_name: str = "clouddrop"
    db_user: str = "clouddrop_admin"
    db_password: str = ""

    def __init__(self):
        try:
            self.db_host = get_param("/clouddrop/db_host")
            self.db_password = get_param("/clouddrop/db_password", decrypt=True)
            self.db_name = get_param("/clouddrop/db_name")
            self.db_user = get_param("/clouddrop/db_user")
            self.s3_bucket = get_param("/clouddrop/s3_bucket")
            self.sqs_url = get_param("/clouddrop/sqs_url")
            self.sns_arn = get_param("/clouddrop/sns_arn")
            try:
                self.proxy_url = get_param("/clouddrop/proxy_url")
            except Exception:
                self.proxy_url = ""
        except Exception as e:
            # Fallback to env vars for local dev
            self.db_host = os.getenv("DB_HOST", "localhost")
            self.db_password = os.getenv("DB_PASSWORD", "")
            self.db_name = os.getenv("DB_NAME", "clouddrop")
            self.db_user = os.getenv("DB_USER", "clouddrop_admin")
            self.s3_bucket = os.getenv("S3_BUCKET", "")
            self.sqs_url = os.getenv("SQS_URL", "")
            self.sns_arn = os.getenv("SNS_ARN", "")
            self.proxy_url = os.getenv("PROXY_URL", "")

settings = Settings()
