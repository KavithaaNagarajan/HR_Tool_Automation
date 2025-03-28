import boto3
import os

# AWS S3 Credentials
AWS_ACCESS_KEY = "AKIAQ364P2C3AL25ZL7K"
AWS_SECRET_KEY = "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"
BUCKET_NAME = "texila-ai-resume"
REGION_NAME = "ap-south-1"
ENDPOINT_URL = "https://s3.ap-south-1.amazonaws.com"

# Initialize S3 Client
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=REGION_NAME,
    endpoint_url=ENDPOINT_URL
)

# Local File Path
local_file_path = r"C:\Users\inc3061\OneDrive - Texila American University\Documents\Resumepath\Data_Flask_Task\Resume_Data\scripts\Header_unwanted_new.csv"

# S3 Key (Destination Path in S3)
s3_file_key = "Function/Header_unwanted_new.csv"  # Change this if you need a different S3 path

def upload_file_to_s3(local_path, bucket_name, s3_key):
    """Uploads a file to S3."""
    if not os.path.exists(local_path):
        print(f"❌ Error: File '{local_path}' does not exist.")
        return

    try:
        s3_client.upload_file(local_path, bucket_name, s3_key)
        print(f"✅ Uploaded successfully: s3://{bucket_name}/{s3_key}")
    except Exception as e:
        print(f"❌ Upload failed: {e}")

# Upload the file
upload_file_to_s3(local_file_path, BUCKET_NAME, s3_file_key)
