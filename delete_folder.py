import boto3

# AWS Credentials (Use environment variables for security)
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

# List of "folders" (prefixes) to delete
folders_to_delete = [
    # "Data_pass/",
    # "JD_uploads/",
    # "converted_pdfs/",
    # "jd_uploads/",
    # "processed/",
    # "processed/processed_pdfs/",
    # "processed_pdfs/",
    # "New_Parser/"
    # "jd_uploads/"
    # "Function/results/"
    # "Function/JD_uploads//",
    # "Function/processed_pdfs/"
    "JD_uploads/"   
   "processed_pdfs/"
]

def delete_s3_folder(folder_prefix):
    """Deletes all objects in the given folder (prefix) from S3."""
    print(f"📂 Deleting folder: {folder_prefix}")

    # List all objects under the folder prefix
    response = s3_client.list_objects_v2(Bucket=BUCKET_NAME, Prefix=folder_prefix)
    
    if "Contents" not in response:
        print(f"✅ Folder '{folder_prefix}' is already empty or does not exist.")
        return
    
    # Collect all object keys
    objects_to_delete = [{"Key": obj["Key"]} for obj in response["Contents"]]

    # Delete objects in batches (max 1000 at a time)
    while objects_to_delete:
        print(f"🗑️ Deleting {len(objects_to_delete)} files from '{folder_prefix}'...")
        response = s3_client.delete_objects(
            Bucket=BUCKET_NAME,
            Delete={"Objects": objects_to_delete[:1000]}
        )
        
        deleted = response.get("Deleted", [])
        for item in deleted:
            print(f"✅ Deleted: {item['Key']}")

        # Continue deleting if there are more than 1000 objects
        objects_to_delete = objects_to_delete[1000:]

# Delete each folder
for folder in folders_to_delete:
    delete_s3_folder(folder)

print("🚀 All specified folders and their contents have been deleted from S3.")
