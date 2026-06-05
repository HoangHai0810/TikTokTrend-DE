import os
import json
import boto3
from botocore.client import Config
from dotenv import load_dotenv

load_dotenv()

S3_ENDPOINT_URL       = os.getenv("S3_ENDPOINT_URL") 
AWS_ACCESS_KEY_ID     = os.getenv("AWS_ACCESS_KEY_ID", "minioadmin")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin")
AWS_REGION            = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME        = os.getenv("S3_BUCKET_NAME", "tiktok-trend-raw")

def get_s3_client():
    """
    Get S3 client.
    """
    params = {
        "aws_access_key_id"    : AWS_ACCESS_KEY_ID,
        "aws_secret_access_key": AWS_SECRET_ACCESS_KEY,
        "region_name"          : AWS_REGION,
        "config"               : Config(signature_version="s3v4")
    }
    
    if S3_ENDPOINT_URL:
        params["endpoint_url"] = S3_ENDPOINT_URL
        
    return boto3.client("s3", **params)

def ensure_bucket_exists(bucket_name=S3_BUCKET_NAME):
    """
    Ensure bucket exists, if not, create it.
    """
    s3 = get_s3_client()
    try:
        s3.head_bucket(Bucket=bucket_name)
    except s3.exceptions.ClientError as e:
        error_code = e.response["Error"]["Code"]
        if error_code == "404":
            print(f"[INFO] Bucket `{bucket_name}` not found. Creating a new bucket")
            # If using MinIO or region us-east-1, do not specify LocationConstraint
            if AWS_REGION == "us-east-1":
                s3.create_bucket(Bucket=bucket_name)
            else:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": AWS_REGION}
                )
            print(f"[SUCCESS] Bucket `{bucket_name}` created successfully.")
        else:
            print(f"[ERROR] Error checking bucket: {e}")
            raise

def upload_json_to_s3(key: str, data_dict: dict, bucket_name=S3_BUCKET_NAME):
    """
    Upload data (dictionary) to S3/MinIO as a JSON file.
    """
    s3 = get_s3_client()
    ensure_bucket_exists(bucket_name)
    
    json_data = json.dumps(data_dict, ensure_ascii=False, indent=4)
    try:
        s3.put_object(
            Bucket      = bucket_name,
            Key         = key,
            Body        = json_data,
            ContentType = "application/json"
        )
        print(f"[SUCCESS] Uploaded file to S3: s3://{bucket_name}/{key}")
    except Exception as e:
        print(f"[ERROR] Failed to upload file to S3: {e}")
        raise

def read_json_from_s3(key: str, bucket_name=S3_BUCKET_NAME) -> dict:
    """
    Read JSON file from S3/MinIO and return a dictionary object.
    """
    s3 = get_s3_client()
    try:
        response = s3.get_object(Bucket=bucket_name, Key=key)
        content  = response["Body"].read().decode("utf-8")
        return json.loads(content)
    except Exception as e:
        print(f"[ERROR] Failed to read file from S3: s3://{bucket_name}/{key}. Error: {e}")
        raise
