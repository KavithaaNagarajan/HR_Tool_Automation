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
 
def list_function_folder_content(bucket_name, prefix_filter='Function/'):

    paginator = s3_client.get_paginator('list_objects_v2')

    pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix_filter)
 
    folders = set()

    files = []
 
    for page in pages:

        for obj in page.get('Contents', []):

            key = obj['Key']

            files.append(key)
 
            # Extract folder paths only under 'Function/'

            parts = key.split('/')

            for i in range(1, len(parts)):

                folder_path = '/'.join(parts[:i])

                if folder_path.startswith(prefix_filter.rstrip('/')):

                    folders.add(folder_path + '/')
 
    print(f"📁 Folders/Subfolders in '{prefix_filter}':")

    for folder in sorted(folders):

        print(f"  - {folder}")
 
    print(f"\n📄 Files in '{prefix_filter}':")

    for file in files:

        print(f"  - {file}")
 
# Run the function

list_function_folder_content(BUCKET_NAME)

 