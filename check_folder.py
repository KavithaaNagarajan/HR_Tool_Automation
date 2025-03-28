import boto3
 
# AWS Credentials
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
 
def list_all_files_and_folders(bucket_name):
    paginator = s3_client.get_paginator('list_objects_v2')
    pages = paginator.paginate(Bucket=bucket_name)
 
    all_files = []
    all_folders = set()
 
    for page in pages:
        for obj in page.get('Contents', []):
            key = obj['Key']
            all_files.append(key)
 
            # Extract folder paths
            parts = key.split('/')
            for i in range(1, len(parts)):
                folder_path = '/'.join(parts[:i])
                all_folders.add(folder_path + '/')
 
    print("📁 Folders/Subfolders:")
    for folder in sorted(all_folders):
        print(f"  - {folder}")
 
    print("\n📄 Files:")
    for file in all_files:
        print(f"  - {file}")
 
# Call the function
list_all_files_and_folders(BUCKET_NAME)