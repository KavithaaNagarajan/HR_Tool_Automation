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
 
# List of file keys to delete
files_to_delete = [
    # "C:\\Users\\inc3061\\OneDrive - Texila American University\\Documents\\Resumepath\\Data_Flask_Task\\New_Parser\\Functions\\Demo_overall_name.csv",
    # "C:\\Users\\inc3061\\OneDrive - Texila American University\\Documents\\Resumepath\\Data_Flask_Task\\New_Parser\\Functions\\cleaned_parsed_headername.csv",
    # "Data_pass/RubiSindhika__today5.pdf",
    # "Data_pass/SaranyaVResume_march_06.pdf",
    # "Data_pass/SaranyaVResume_march_today5.pdf",
    # "JD_uploads/sql_d.csv",
    # "converted_pdfs/H-Jobin Jimmy - EA 1.pdf",
    # "converted_pdfs/Kavitha Nagarajan.docx",
    # "converted_pdfs/Liyamin+updated - EA.pdf",
    # "converted_pdfs/converted_H-Jobin Jimmy - EA 1.pdf.pdf",
    # "jd_uploads/Campaign_Executive_JD.csv",
    # "jd_uploads/EnrillmentAdvisor_JD.csv",
    # "jd_uploads/Python_developer_JD.csv",
    # "jd_uploads/Sql_JD.csv",
    # "parsed_headername.csv",
    # "processed/processed_pdfs/RubiSindhika__today5.pdf",
    # "processed/processed_pdfs/SaranyaVResume_march_06.pdf",
    # "processed/processed_pdfs/SaranyaVResume_march_today5.pdf",
    # "processed_pdfs/Compare_exp.csv",
    # "processed_pdfs/Demo_overall_name.csv",
    # "processed_pdfs/Fileexp_data.csv",
    # "processed_pdfs/H-Jobin Jimmy - EA 1.pdf",
    # "processed_pdfs/JD_Match.csv",
    # "processed_pdfs/Kavitha Nagarajan.pdf",
    # "processed_pdfs/Liyamin+updated - EA.pdf",
    # "processed_pdfs/Randomexp_data.csv",
    # "processed_pdfs/RubiSindhika__today5.pdf",
    # "processed_pdfs/SaranyaVResume_march_06.pdf",
    # "processed_pdfs/SaranyaVResume_march_today5.pdf",
    # "processed_pdfs/csv_output_experience.csv",
    # "processed_pdfs/email.csv",
    # "processed_pdfs/experience_data.csv",
    # "processed_pdfs/final_experience_data.csv",
    # "processed_pdfs/overall_Details.csv",
    # "processed_pdfs/phone_numbers.csv",
    # "test_trainname_demo.csv",
    # "New_Parser/"
    "JD_uploads/Campaign_Executive_JD.csv",
    "processed_pdfs/H-Jobin Jimmy - EA 1.pdf",
    "processed_pdfs/Kavitha Nagarajan.pdf",
    "processed_pdfs/Liyamin+updated - EA.pdf",
    "processed_pdfs/RubiSindhika__today5.pdf",
    "processed_pdfs/SaranyaVResume_march_06.pdf",
    "processed_pdfs/SaranyaVResume_march_today5.pdf",
    "processed_pdfs/overall_Details.csv"
]
 
# Create delete objects list
delete_objects = [{'Key': key} for key in files_to_delete]
 
# Perform bulk delete (max 1000 at a time)
response = s3_client.delete_objects(
    Bucket=BUCKET_NAME,
    Delete={'Objects': delete_objects}
)
 
# Confirm deleted files
deleted = response.get('Deleted', [])
for item in deleted:
    print(f"🗑️ Deleted: {item['Key']}")