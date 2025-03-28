import os
import boto3

# AWS S3 Setup
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

def upload_folder_to_s3(local_folder_path, s3_prefix):
    """Uploads a local folder to S3"""
    for root, _, files in os.walk(local_folder_path):
        for filename in files:
            local_path = os.path.join(root, filename)
            relative_path = os.path.relpath(local_path, start=local_folder_path)
            s3_key = f"{s3_prefix}/{relative_path}".replace("\\", "/")  # Ensure S3-compatible paths

            try:
                s3_client.upload_file(local_path, BUCKET_NAME, s3_key)
                print(f"✅ Uploaded: s3://{BUCKET_NAME}/{s3_key}")
            except Exception as e:
                print(f"❌ Failed to upload {s3_key}: {e}")

# ✅ Use Raw Strings (r"") to Fix Windows Path Issues
folder_mappings = {
    r"C:\Users\inc3061\OneDrive - Texila American University\Documents\Resumepath\Data_Flask_Task\New_Parser\Functions": "Function",
    r"C:\Users\inc3061\OneDrive - Texila American University\Documents\Resumepath\Data_Flask_Task\New_Parser\Functions\JD_uploads": "JD_uploads",
    r"C:\Users\inc3061\OneDrive - Texila American University\Documents\Resumepath\Data_Flask_Task\New_Parser\Functions\processed_pdfs": "processed_pdfs"
}

# Upload each folder
for local_folder, s3_prefix in folder_mappings.items():
    if os.path.isdir(local_folder):
        print(f"🚀 Uploading '{local_folder}' to 's3://{BUCKET_NAME}/{s3_prefix}/'")
        upload_folder_to_s3(local_folder, s3_prefix)

print("🎉 All folders uploaded successfully!")
