


import os
import shutil
import comtypes.client
import pythoncom  # Fixes "CoInitialize has not been called"
from PIL import Image
from fpdf import FPDF
from docx import Document
import re
import fitz  # PyMuPDF for extracting text from PDFs
import pandas as pd
import spacy
from pdfminer.high_level import extract_text
from PyPDF2 import PdfReader
import pdfplumber
from fuzzywuzzy import fuzz
import streamlit as st
import boto3  # For AWS S3 Upload and Download
from io import BytesIO
 
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
 
# Font Path in S3 is unsupported for FPDF, still needs local font for fallback
FONT_PATH = r"C:\\Users\\inc3061\\Downloads\\dejavu-fonts-ttf-2.37\\ttf\\DejaVuSans.ttf"
 
class UnicodePDF(FPDF):
    def header(self):
        self.set_font("Arial", "", 12)
        self.cell(0, 10, "Converted PDF", ln=True, align="C")
 
class FileConverter:
    def __init__(self, s3_bucket, s3_output_prefix="Function/processed_pdfs/"):
        self.bucket = s3_bucket
        self.output_prefix = s3_output_prefix
 
    def convert_to_pdf(self, uploaded_file, file_ext):
        filename = uploaded_file.name
        output_key = f"{self.output_prefix}_{filename}.pdf"
 
        try:
            if file_ext in ["pdf", "jpg", "jpeg", "png"]:
                img_or_pdf = Image.open(uploaded_file) if file_ext != "pdf" else None
                output_stream = BytesIO()
 
                if img_or_pdf:
                    img_or_pdf.convert("RGB").save(output_stream, "PDF")
                else:
                    output_stream.write(uploaded_file.read())
 
                output_stream.seek(0)
                s3_client.upload_fileobj(output_stream, self.bucket, output_key)
                return output_key
 
            elif file_ext in ["doc", "docx"]:
                temp_path = f"/tmp/{filename}"
                with open(temp_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
 
                output_pdf_path = f"/tmp/{filename}.pdf"
                try:
                    pythoncom.CoInitialize()
                    word = comtypes.client.CreateObject("Word.Application")
                    doc = word.Documents.Open(os.path.abspath(temp_path))
                    doc.SaveAs(os.path.abspath(output_pdf_path), FileFormat=17)
                    doc.Close(False)
                    word.Quit()
 
                    with open(output_pdf_path, "rb") as f:
                        s3_client.upload_fileobj(f, self.bucket, output_key)
 
                    return output_key
 
                except Exception as e:
                    print(f"MS Word conversion failed: {e}")
                    return f"Error converting DOCX: {e}"
 
            else:
                return f"Unsupported file format: {file_ext}"
 
        except Exception as e:
            return f"Error during conversion: {str(e)}"
 
# Streamlit UI
st.title("Resume Parser")
 
# Upload and Convert File
st.header("File for PDF Conversion")
uploaded_file = st.file_uploader("Upload a file", type=["pdf", "jpg", "jpeg", "png", "doc", "docx"])
if uploaded_file:
    file_ext = uploaded_file.name.split(".")[-1].lower()
    converter = FileConverter(BUCKET_NAME)
    s3_pdf_key = converter.convert_to_pdf(uploaded_file, file_ext)
 
    if s3_pdf_key and "Error" not in s3_pdf_key:
        st.success("File converted successfully!")
        st.info(f"Uploaded to S3: {s3_pdf_key}")
    else:
        st.error(f"Conversion failed: {s3_pdf_key}")
 
# Upload JD CSV to S3
st.header("Job Description (CSV File) Uploader")
jd_uploaded_file = st.file_uploader("Upload JD file", type=["csv"], key="jd")
if jd_uploaded_file:
    jd_s3_key = f"Function/JD_uploads/{jd_uploaded_file.name}"
    s3_client.upload_fileobj(jd_uploaded_file, BUCKET_NAME, jd_s3_key)
    st.success("JD file uploaded successfully!")
    st.info(f"JD file uploaded to S3: {jd_s3_key}")


import boto3
import os
import io
import re
import pandas as pd
import fitz  # PyMuPDF
 
# AWS S3 Configuration
AWS_ACCESS_KEY = "AKIAQ364P2C3AL25ZL7K"
AWS_SECRET_KEY = "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"
BUCKET_NAME = "texila-ai-resume"
REGION_NAME = "ap-south-1"
ENDPOINT_URL = "https://s3.ap-south-1.amazonaws.com"
 
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY,
    aws_secret_access_key=AWS_SECRET_KEY,
    region_name=REGION_NAME,
    endpoint_url=ENDPOINT_URL
)
 
class FileCleaner:
    def __init__(self, s3_pdf_prefix, s3_csv_key, s3_output_key):
        """
        Initializes the FileCleaner class with S3 keys and prefixes.
 
        Args:
        - s3_pdf_prefix (str): S3 prefix to the folder containing PDF files.
        - s3_csv_key (str): S3 key to the CSV file containing unwanted words.
        - s3_output_key (str): S3 key where cleaned results will be saved.
        """
        self.s3_pdf_prefix = s3_pdf_prefix
        self.s3_csv_key = s3_csv_key
        self.s3_output_key = s3_output_key
 
        self.unwanted_words = self.load_unwanted_words()
        self.data = []
 
    def load_unwanted_words(self):
        """Loads unwanted words from a CSV file stored in S3."""
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=self.s3_csv_key)
            df = pd.read_csv(io.BytesIO(response['Body'].read()))
            return df['Unwanted Word'].dropna().tolist()
        except Exception as e:
            print(f"Error loading unwanted words from S3 CSV: {e}")
            return []
 
    def clean_name_from_filename(self, filename):
        name_with_extension = os.path.splitext(filename)[0]
        unwanted_pattern = r"(" + "|".join(map(re.escape, self.unwanted_words)) + r")"
        additional_patterns = [r"\d+", r"[^\w\s]", r"\bym\b"]
        name_with_extension = re.sub(unwanted_pattern, '', name_with_extension, flags=re.IGNORECASE)
        for pattern in additional_patterns:
            name_with_extension = re.sub(pattern, '', name_with_extension)
        cleaned_name = re.sub(r"\s+", " ", name_with_extension).strip()
        return cleaned_name
 
    def extract_email(self, text):
        email_regex = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        match = re.search(email_regex, text)
        return match.group(0) if match else None
 
    def extract_phone_number_from_text(self, text):
        phone_pattern = r'\+?\d{1,3}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{1,4}[\s\-]?\d{1,4}[\s\-]?\d{1,9}'
        matches = re.findall(phone_pattern, text)
        for match in matches:
            phone_number = re.sub(r'[^\d+]', '', match)
            if len(phone_number) >= 10:
                return phone_number
        return None
 
    def extract_text_from_pdf(self, file_bytes):
        text = ""
        try:
            pdf_reader = fitz.open(stream=file_bytes, filetype="pdf")
            for page in pdf_reader:
                text += page.get_text("text") + "\n"
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
        return text.strip()
 
    def process_files(self):
        """Processes PDF files stored in S3."""
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=BUCKET_NAME, Prefix=self.s3_pdf_prefix)
 
            for page in page_iterator:
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    if key.lower().endswith('.pdf'):
                        filename = os.path.basename(key)
                        cleaned_name = self.clean_name_from_filename(filename)
 
                        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
                        file_bytes = response['Body'].read()
 
                        text = self.extract_text_from_pdf(file_bytes)
                        email = self.extract_email(text)
                        phone_number = self.extract_phone_number_from_text(text)
 
                        self.data.append({
                            'Filename': filename,
                            'Name from Filename': cleaned_name,
                            'Email': email,
                            'Phone Number': phone_number
                        })
 
        except Exception as e:
            print(f"Error processing PDF files from S3: {e}")
 
    def save_results(self):
        try:
            df = pd.DataFrame(self.data)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            s3_client.put_object(Bucket=BUCKET_NAME, Key=self.s3_output_key, Body=csv_buffer.getvalue())
            print(f"Results saved to S3: {self.s3_output_key}")
        except Exception as e:
            print(f"Error saving results to S3: {e}")
 
# Example usage
if __name__ == "__main__":
    s3_pdf_prefix = "Function/processed_pdfs/"
    s3_csv_key = "Function/Filename_unwanted.csv"
    s3_output_key = "Function/test_trainname_demo.csv"
 
    file_cleaner = FileCleaner(s3_pdf_prefix, s3_csv_key, s3_output_key)
    file_cleaner.process_files()
    file_cleaner.save_results()

import os
import re
import boto3
import pandas as pd
import spacy
import io
from pdfminer.high_level import extract_text
from docx import Document
from botocore.exceptions import NoCredentialsError

# AWS S3 Configuration
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

class HeaderExtractor:
    def __init__(self, s3_pdf_prefix, s3_output_key, unwanted_words=None, evaluation_warning=None):
        """
        Initializes the HeaderExtractor with S3 paths and optional parameters.

        Args:
        - s3_pdf_prefix (str): The S3 prefix (folder path) containing resumes.
        - s3_output_key (str): The S3 key where cleaned results will be saved.
        - unwanted_words (list): List of words to be avoided in the first line.
        - evaluation_warning (str): The warning message to avoid in the first line.
        """
        self.s3_pdf_prefix = s3_pdf_prefix
        self.s3_output_key = s3_output_key
        self.nlp = spacy.load("en_core_web_sm")  # Load spaCy model for NER
        self.unwanted_words = unwanted_words or [
            "CURRICULUM VITAE", "resume", "contact", "personal details", "Professional Skills", 
            "Name", "SUMMARY", "SKILLS", "EXPERIENCE"
        ]
        self.evaluation_warning = evaluation_warning or "Evaluation Warning: The document was created with Spire.Doc for Python."
        self.data = []

    def extract_text_from_pdf(self, file_bytes):
        """Extracts text from a PDF file."""
        try:
            return extract_text(io.BytesIO(file_bytes))
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
            return ""

    def extract_text_from_docx(self, file_bytes):
        """Extracts text from a DOCX file."""
        try:
            doc = Document(io.BytesIO(file_bytes))
            return "\n".join([para.text for para in doc.paragraphs])
        except Exception as e:
            print(f"Error extracting text from DOCX: {e}")
            return ""

    def clean_and_get_valid_line(self, text):
        """Cleans the text and returns the first valid line."""
        lines = text.strip().split("\n")
        for line in lines:
            line = line.strip()
            if line and not any(word.lower() in line.lower() for word in self.unwanted_words) and line != self.evaluation_warning:
                return line
        return "No valid line found."

    def extract_name_using_spacy(self, text):
        """Extracts name using spaCy's Named Entity Recognition (NER)."""
        doc = self.nlp(text)
        names = [ent.text for ent in doc.ents if ent.label_ == "PERSON"]
        return names[0] if names else None

    def extract_name_using_regex(self, first_line):
        """Extracts name using regex from the first valid line."""
        name_pattern = r'\b([A-Z][a-z]+(?: [A-Z]\.)? [A-Z][a-z]+|[A-Z][a-z]+(?: [A-Z][a-z]+)?)\b'
        matches = re.findall(name_pattern, first_line)
        return matches[0] if matches else None

    def extract_full_name(self, text):
        """Extracts full name from the text using NER and Regex."""
        valid_line = self.clean_and_get_valid_line(text)
        full_name = self.extract_name_using_spacy(valid_line) or self.extract_name_using_regex(valid_line)
        return full_name or "Full name not found.", valid_line

    def process_files_from_s3(self):
        """Processes all PDF & DOCX files from S3."""
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=BUCKET_NAME, Prefix=self.s3_pdf_prefix)

            for page in page_iterator:
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    if key.lower().endswith(('.pdf', '.docx')):
                        print(f"Processing file: {key}")
                        
                        # Fetch file from S3
                        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
                        file_bytes = response['Body'].read()

                        # Extract text
                        text = self.extract_text_from_pdf(file_bytes) if key.lower().endswith('.pdf') else self.extract_text_from_docx(file_bytes)

                        # Extract name
                        full_name, extracted_line = self.extract_full_name(text)

                        # Store result
                        self.data.append({"Filename": os.path.basename(key), "Full_Name": full_name, "Extracted_Line": extracted_line})
        
        except Exception as e:
            print(f"Error processing files from S3: {e}")

    def save_results_to_s3(self):
        """Saves the results DataFrame to a CSV file and uploads it to S3."""
        try:
            df = pd.DataFrame(self.data)
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            
            # Upload to S3
            s3_client.put_object(Bucket=BUCKET_NAME, Key=self.s3_output_key, Body=csv_buffer.getvalue())
            print(f"Results saved to S3: s3://{BUCKET_NAME}/{self.s3_output_key}")
        
        except NoCredentialsError:
            print("Error: AWS Credentials not found.")
        except Exception as e:
            print(f"Error saving results to S3: {e}")

# Example usage
if __name__ == "__main__":
    s3_pdf_prefix = "Function/processed_pdfs/"  # S3 folder containing resumes
    s3_output_key = "Function/parsed_headername.csv"  # Output file in S3

    header_extractor = HeaderExtractor(s3_pdf_prefix, s3_output_key)
    
    # Process resumes
    header_extractor.process_files_from_s3()

    # Save extracted data
    header_extractor.save_results_to_s3()

import os
import re
import boto3
import pandas as pd
import io
from botocore.exceptions import NoCredentialsError

# AWS S3 Configuration
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

class ResumeCleaner:
    def __init__(self, s3_unwanted_words_key, s3_input_csv_key, s3_output_csv_key):
        """
        Initializes ResumeCleaner with S3 paths.

        Args:
        - s3_unwanted_words_key (str): S3 key for unwanted words CSV.
        - s3_input_csv_key (str): S3 key for input CSV containing extracted lines.
        - s3_output_csv_key (str): S3 key where the cleaned CSV will be saved.
        """
        self.s3_unwanted_words_key = s3_unwanted_words_key
        self.s3_input_csv_key = s3_input_csv_key
        self.s3_output_csv_key = s3_output_csv_key
        self.unwanted_words = self.read_unwanted_words()
        self.df = self.load_input_csv()

    def read_unwanted_words(self):
        """Reads unwanted words from an S3 CSV file."""
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=self.s3_unwanted_words_key)
            unwanted_df = pd.read_csv(io.BytesIO(response['Body'].read()))
            return unwanted_df['word'].dropna().tolist() if 'word' in unwanted_df.columns else []
        except Exception as e:
            print(f"Error loading unwanted words from S3: {e}")
        return []

    def load_input_csv(self):
        """Loads input CSV from S3."""
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=self.s3_input_csv_key)
            df = pd.read_csv(io.BytesIO(response['Body'].read()))
            if df.empty:
                print(f"⚠ Warning: Input CSV '{self.s3_input_csv_key}' is empty.")
            return df
        except Exception as e:
            print(f"Error loading input CSV from S3: {e}")
        return pd.DataFrame()

    def clean_extracted_line(self, extracted_line):
        """Cleans an extracted line by removing unwanted elements."""
        if not isinstance(extracted_line, str):
            return ""
        
        # Remove emails
        extracted_line = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '', extracted_line)
        
        # Remove phone numbers
        extracted_line = re.sub(r'(\+?\(?\d{1,4}\)?[\s\-]?)?(\(?\d{1,4}\)?[\s\-]?\d{1,3}[\s\-]?\d{3}[\s\-]?\d{4}|\d{10})', '', extracted_line)
        
        # Remove text inside parentheses
        extracted_line = re.sub(r'\(.*?\)', '', extracted_line)
        
        # Remove unwanted words
        for word in self.unwanted_words:
            extracted_line = re.sub(r'\b' + re.escape(word) + r'\b', '', extracted_line, flags=re.IGNORECASE)
        
        # Keep only alphabetic words
        extracted_line = re.sub(r'[^a-zA-Z\s]', '', extracted_line)
        
        return extracted_line.strip()

    def clean_resumes(self):
        """Cleans the 'Extracted_Line' column in the dataset."""
        if not self.df.empty and 'Extracted_Line' in self.df.columns:
            self.df['Cleaned_Extracted_Line'] = self.df['Extracted_Line'].astype(str).apply(self.clean_extracted_line)
        else:
            print("Error: No valid 'Extracted_Line' column found or DataFrame is empty.")

    def save_cleaned_resumes_to_s3(self):
        """Saves the cleaned data to S3."""
        if self.df.empty:
            print("Error: No data to save to CSV.")
            return
        
        try:
            csv_buffer = io.StringIO()
            self.df.to_csv(csv_buffer, index=False)
            
            # Upload to S3
            s3_client.put_object(Bucket=BUCKET_NAME, Key=self.s3_output_csv_key, Body=csv_buffer.getvalue())
            print(f"Cleaned resumes saved to S3: s3://{BUCKET_NAME}/{self.s3_output_csv_key}")

        except NoCredentialsError:
            print("Error: AWS Credentials not found.")
        except Exception as e:
            print(f"Error saving cleaned resumes to S3: {e}")

# Example usage
if __name__ == "__main__":
    s3_unwanted_words_key = "Function/Header_unwanted_new.csv"  # S3 path for unwanted words
    s3_input_csv_key = "Function/parsed_headername.csv"  # S3 path for input CSV
    s3_output_csv_key = "Function/cleaned_parsed_headername.csv"  # S3 output path

    resume_cleaner = ResumeCleaner(s3_unwanted_words_key, s3_input_csv_key, s3_output_csv_key)
    
    # Clean resumes
    resume_cleaner.clean_resumes()

    # Save cleaned resumes
    resume_cleaner.save_cleaned_resumes_to_s3()

import os
import re
import boto3
import pandas as pd
import io
from botocore.exceptions import NoCredentialsError

# AWS S3 Configuration
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

class NameComparator:
    def __init__(self, s3_filename_key, s3_headername_key, s3_output_key):
        """
        Initializes the NameComparator with S3 paths for filename CSV, headername CSV, and output CSV.

        Args:
        - s3_filename_key (str): S3 key for filename CSV.
        - s3_headername_key (str): S3 key for headername CSV.
        - s3_output_key (str): S3 key for output CSV.
        """
        self.s3_filename_key = s3_filename_key
        self.s3_headername_key = s3_headername_key
        self.s3_output_key = s3_output_key

        # Load data from S3
        self.filename_df = self.load_csv_from_s3(self.s3_filename_key, "Filename CSV")
        self.headername_df = self.load_csv_from_s3(self.s3_headername_key, "Headername CSV")

    def load_csv_from_s3(self, s3_key, label):
        """Loads a CSV file from S3 and returns a DataFrame."""
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
            df = pd.read_csv(io.BytesIO(response['Body'].read()))
            if df.empty:
                print(f"⚠ Warning: {label} '{s3_key}' is empty.")
            return df
        except Exception as e:
            print(f"Error loading {label} from S3 ('{s3_key}'): {e}")
            return pd.DataFrame()

    def clean_extracted_line(self):
        """Cleans the 'Cleaned_Extracted_Line' column."""
        if not self.headername_df.empty:
            self.headername_df['Cleaned_Extracted_Line'] = self.headername_df['Cleaned_Extracted_Line'].apply(
                lambda x: '' if len(str(x)) >= 3 and len(str(x)) < 10 else x
            )

    def merge_dataframes(self):
        """Merges the two DataFrames on the 'Filename' column."""
        if self.filename_df.empty or self.headername_df.empty:
            print("Error: One or both DataFrames are empty. Cannot merge.")
            return pd.DataFrame()

        combined_df = pd.merge(self.filename_df, self.headername_df, on='Filename', how='inner')
        return combined_df[['Filename', 'Name from Filename', 'Cleaned_Extracted_Line', 'Email', 'Phone Number']]

    def check_match(self, row):
        """Compares 'Name from Filename' and 'Cleaned_Extracted_Line'."""
        name_from_filename = str(row['Name from Filename']).lower() if pd.notna(row['Name from Filename']) else ''
        cleaned_line = str(row['Cleaned_Extracted_Line']).lower() if pd.notna(row['Cleaned_Extracted_Line']) else ''
        
        if pd.isna(row['Name from Filename']) and pd.isna(row['Cleaned_Extracted_Line']):
            return ''
        if pd.isna(row['Name from Filename']):
            return row['Cleaned_Extracted_Line']
        if pd.isna(row['Cleaned_Extracted_Line']):
            return row['Name from Filename']
        if cleaned_line in name_from_filename:
            return row['Cleaned_Extracted_Line']
        return row['Name from Filename']

    def compare_names(self):
        """Applies the name comparison logic."""
        merged_df = self.merge_dataframes()
        if not merged_df.empty:
            merged_df['Result'] = merged_df.apply(self.check_match, axis=1)
        else:
            print("Error: No data available to compare.")
        return merged_df

    def save_comparison_results_to_s3(self, final_df):
        """Saves the comparison results to a CSV file and uploads it to S3."""
        if final_df.empty:
            print("Error: No comparison results to save.")
            return
        
        try:
            csv_buffer = io.StringIO()
            final_df.to_csv(csv_buffer, index=False)
            
            # Upload to S3
            s3_client.put_object(Bucket=BUCKET_NAME, Key=self.s3_output_key, Body=csv_buffer.getvalue())
            print(f"Comparison results saved to S3: s3://{BUCKET_NAME}/{self.s3_output_key}")

        except NoCredentialsError:
            print("Error: AWS Credentials not found.")
        except Exception as e:
            print(f"Error saving comparison results to S3: {e}")

# Example usage
if __name__ == "__main__":
    s3_filename_key = "Function/test_trainname_demo.csv"  # S3 path for filename CSV
    s3_headername_key = "Function/cleaned_parsed_headername.csv"  # S3 path for headername CSV
    s3_output_key = "Function/Demo_overall_name.csv"  # S3 output file

    # Initialize NameComparator
    name_comparator = NameComparator(s3_filename_key, s3_headername_key, s3_output_key)

    # Clean extracted line
    name_comparator.clean_extracted_line()

    # Compare names
    final_df = name_comparator.compare_names()

    # Save results to S3
    name_comparator.save_comparison_results_to_s3(final_df)

import os
import re
import boto3
import pandas as pd
import io
from PyPDF2 import PdfReader
from botocore.exceptions import NoCredentialsError

# AWS S3 Configuration
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

class EmailExtractor:
    def __init__(self, s3_pdf_prefix, s3_output_key):
        """
        Initializes the EmailExtractor with S3 paths.

        Args:
        - s3_pdf_prefix (str): The S3 prefix (folder path) containing PDFs.
        - s3_output_key (str): The S3 key where extracted emails will be saved.
        """
        self.s3_pdf_prefix = s3_pdf_prefix
        self.s3_output_key = s3_output_key

    @staticmethod
    def extract_first_email(text):
        """Extracts the first email from the given text."""
        email_pattern = r"([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)"
        emails = re.findall(email_pattern, text)
        return emails[0] if emails else None

    def extract_text_from_pdf(self, file_bytes):
        """Extracts text from a PDF file."""
        text = ""
        try:
            pdf_reader = PdfReader(io.BytesIO(file_bytes))
            for page in pdf_reader.pages:
                extracted_text = page.extract_text()
                if extracted_text:
                    text += extracted_text
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
        return text.strip()

    def extract_first_email_from_s3(self):
        """Extracts the first email from each PDF file stored in S3."""
        results = []
        total_files = 0
        processed_files = 0

        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=BUCKET_NAME, Prefix=self.s3_pdf_prefix)

            for page in page_iterator:
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    total_files += 1

                    if key.lower().endswith('.pdf'):
                        print(f"Processing file: {key}")

                        # Fetch file from S3
                        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
                        file_bytes = response['Body'].read()

                        # Extract text and email
                        text = self.extract_text_from_pdf(file_bytes)
                        first_email = self.extract_first_email(text)

                        if first_email:
                            results.append({'Filename': os.path.basename(key), 'first_email': first_email})
                        processed_files += 1

        except Exception as e:
            print(f"Error processing PDFs from S3: {e}")

        print(f"Total files scanned: {total_files}")
        print(f"Processed files with emails: {processed_files}")

        return pd.DataFrame(results)

    def save_emails_to_s3(self, emails_df):
        """Saves the extracted emails to S3 as a CSV file."""
        if emails_df.empty:
            print("Warning: No emails found. Skipping file upload.")
            return

        try:
            csv_buffer = io.StringIO()
            emails_df.to_csv(csv_buffer, index=False)

            # Upload to S3
            s3_client.put_object(Bucket=BUCKET_NAME, Key=self.s3_output_key, Body=csv_buffer.getvalue())
            print(f"Extracted emails saved to S3: s3://{BUCKET_NAME}/{self.s3_output_key}")

        except NoCredentialsError:
            print("Error: AWS Credentials not found.")
        except Exception as e:
            print(f"Error saving emails to S3: {e}")

# Example usage
if __name__ == "__main__":
    s3_pdf_prefix = "Function/processed_pdfs/"  # S3 folder containing resumes
    s3_output_key = "Function/email.csv"  # Output file in S3

    # Initialize EmailExtractor
    email_extractor = EmailExtractor(s3_pdf_prefix, s3_output_key)

    # Extract emails from S3 PDFs
    emails_df = email_extractor.extract_first_email_from_s3()
    
    # Save extracted emails to S3
    email_extractor.save_emails_to_s3(emails_df)


import os
import re
import boto3
import pandas as pd
import io
from PyPDF2 import PdfReader
from botocore.exceptions import NoCredentialsError

# AWS S3 Configuration
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

class PhoneNumberExtractor:
    def __init__(self, s3_pdf_prefix, s3_output_key):
        """
        Initializes the PhoneNumberExtractor with S3 paths.

        Args:
        - s3_pdf_prefix (str): The S3 prefix (folder path) containing PDFs.
        - s3_output_key (str): The S3 key where extracted phone numbers will be saved.
        """
        self.s3_pdf_prefix = s3_pdf_prefix
        self.s3_output_key = s3_output_key

    @staticmethod
    def extract_phone_number_from_text(text):
        """Extracts phone numbers from a given text using regex."""
        phone_pattern = r'\+?\d{1,4}[\s\-]?\(?\d{1,4}\)?[\s\-]?\d{1,3}[\s\-]?\d{3}[\s\-]?\d{4}|\d{10}'
        phone_matches = re.findall(phone_pattern, text)

        phone_numbers = []
        for match in phone_matches:
            phone_number = re.sub(r'\D', '', match)  # Remove non-numeric characters
            if len(phone_number) >= 10:  # Valid phone numbers should have at least 10 digits
                phone_numbers.append(phone_number)

        return phone_numbers if phone_numbers else None

    def extract_text_from_pdf(self, file_bytes):
        """Extracts text from a PDF file."""
        text = ""
        try:
            pdf_reader = PdfReader(io.BytesIO(file_bytes))
            for page in pdf_reader.pages:
                extracted_text = page.extract_text()
                if extracted_text:
                    text += extracted_text
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
        return text.strip()

    def extract_phone_numbers_from_s3(self):
        """Extracts phone numbers from each PDF file stored in S3."""
        results = []
        total_files = 0
        processed_files = 0

        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=BUCKET_NAME, Prefix=self.s3_pdf_prefix)

            for page in page_iterator:
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    total_files += 1

                    if key.lower().endswith('.pdf'):
                        print(f"Processing file: {key}")

                        # Fetch file from S3
                        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=key)
                        file_bytes = response['Body'].read()

                        # Extract text and phone numbers
                        text = self.extract_text_from_pdf(file_bytes)
                        phone_numbers = self.extract_phone_number_from_text(text)

                        if phone_numbers:
                            first_phone_number = phone_numbers[0] if phone_numbers else None
                            results.append({
                                'Filename': os.path.basename(key),
                                'phone_numbers': phone_numbers,
                                'first_phone_number': first_phone_number
                            })
                            processed_files += 1

        except Exception as e:
            print(f"Error processing PDFs from S3: {e}")

        print(f"Total files scanned: {total_files}")
        print(f"Processed files with phone numbers: {processed_files}")

        return pd.DataFrame(results)

    def process_phone_numbers(self, row):
        """
        Processes phone numbers based on custom logic.

        Args:
        - row (pd.Series): A row from the DataFrame containing phone numbers.

        Returns:
        - str: The processed phone number.
        """
        first_phone_number = row['first_phone_number']
        phone_numbers = row['phone_numbers']

        cleaned_phone_numbers = [re.sub(r'\D', '', num) for num in phone_numbers]

        if not cleaned_phone_numbers:
            return None

        # Custom logic based on phone number length
        if len(first_phone_number) in [4, 6]:  
            return cleaned_phone_numbers[-1][-10:] if len(cleaned_phone_numbers[-1]) >= 10 else None
        elif len(first_phone_number) > 13:
            return cleaned_phone_numbers[-1][-10:] if len(cleaned_phone_numbers[-1]) >= 10 else None
        else:
            return cleaned_phone_numbers[0]

    def save_phone_numbers_to_s3(self, phone_numbers_df):
        """Saves the extracted phone numbers to S3 as a CSV file."""
        if phone_numbers_df.empty:
            print("⚠ Warning: No phone numbers found. Skipping file upload.")
            return

        try:
            csv_buffer = io.StringIO()
            phone_numbers_df.to_csv(csv_buffer, index=False)

            # Upload to S3
            s3_client.put_object(Bucket=BUCKET_NAME, Key=self.s3_output_key, Body=csv_buffer.getvalue())
            print(f"Extracted phone numbers saved to S3: s3://{BUCKET_NAME}/{self.s3_output_key}")

        except NoCredentialsError:
            print("Error: AWS Credentials not found.")
        except Exception as e:
            print(f"Error saving phone numbers to S3: {e}")

# Example usage
if __name__ == "__main__":
    s3_pdf_prefix = "Function/processed_pdfs/"  # S3 folder containing resumes
    s3_output_key = "Function/phone_numbers.csv"  # Output file in S3

    # Initialize PhoneNumberExtractor
    phone_extractor = PhoneNumberExtractor(s3_pdf_prefix, s3_output_key)

    # Extract phone numbers from S3 PDFs
    phone_numbers_df = phone_extractor.extract_phone_numbers_from_s3()
    
    # Process phone numbers
    if not phone_numbers_df.empty:
        phone_numbers_df['processed_phone_number'] = phone_numbers_df.apply(phone_extractor.process_phone_numbers, axis=1)
        phone_extractor.save_phone_numbers_to_s3(phone_numbers_df)
    else:
        print("No phone numbers found in S3 PDFs.")

import os
import re
import boto3
import pandas as pd
import io
from botocore.exceptions import NoCredentialsError

# AWS S3 Configuration
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

class DataMerger:
    def __init__(self, s3_phone_numbers_key, s3_email_key, s3_name_key, s3_output_key):
        """
        Initializes the DataMerger with S3 keys.

        Args:
        - s3_phone_numbers_key (str): S3 key for phone numbers CSV.
        - s3_email_key (str): S3 key for email CSV.
        - s3_name_key (str): S3 key for name CSV.
        - s3_output_key (str): S3 key where the merged data will be saved.
        """
        self.s3_phone_numbers_key = s3_phone_numbers_key
        self.s3_email_key = s3_email_key
        self.s3_name_key = s3_name_key
        self.s3_output_key = s3_output_key

        required_columns = {
            "phone_numbers": ["Filename", "phone_numbers", "first_phone_number"],
            "email": ["Filename", "first_email"],
            "name": ["Filename", "Name from Filename", "Cleaned_Extracted_Line", "Result", "Email", "Phone Number"]
        }

        self.phone_numbers_df = self.safe_read_csv(s3_phone_numbers_key, required_columns["phone_numbers"])
        self.email_df = self.safe_read_csv(s3_email_key, required_columns["email"])
        self.name_df = self.safe_read_csv(s3_name_key, required_columns["name"])

    def safe_read_csv(self, s3_key, required_columns):
        """Reads a CSV file from S3, returning an empty DataFrame if the file is missing or unreadable."""
        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
            df = pd.read_csv(io.BytesIO(response['Body'].read()))
        except (s3_client.exceptions.NoSuchKey, pd.errors.EmptyDataError, FileNotFoundError):
            print(f"⚠ Warning: File '{s3_key}' not found or empty. Creating empty DataFrame.")
            df = pd.DataFrame(columns=required_columns)

        for col in required_columns:
            if col not in df.columns:
                df[col] = None  
        
        return df

    def clean_and_prepare_data(self):
        """Cleans column names and prepares data for merging."""
        self.phone_numbers_df.rename(columns={'phone_numbers': 'PhoneNumbers_List', 
                                              'first_phone_number': 'Candidates_PhoneNumber'}, inplace=True)
        self.phone_numbers_df = self.phone_numbers_df[['Filename', 'PhoneNumbers_List', 'Candidates_PhoneNumber']]

        self.email_df.rename(columns={'first_email': 'Candidates_Email'}, inplace=True)

        self.name_df.rename(columns={'Name from Filename': 'Name_from_File',
                                     'Cleaned_Extracted_Line': 'Header_Name', 
                                     'Result': 'Candidates_Name', 
                                     'Email': 'Header_Emails', 
                                     'Phone Number': 'Header_Phone'}, inplace=True)
        self.name_df = self.name_df[['Filename', 'Candidates_Name', 'Name_from_File', 'Header_Name', 'Header_Emails', 'Header_Phone']]

    def merge_dataframes(self):
        """Merges the three DataFrames on 'Filename'."""
        merged_df = self.name_df.merge(self.email_df, on='Filename', how='left') \
                                .merge(self.phone_numbers_df, on='Filename', how='left')

        # Fill missing emails & phone numbers from available data
        merged_df['Header_Emails'] = merged_df['Header_Emails'].fillna(merged_df['Candidates_Email'])
        merged_df['Candidates_PhoneNumber'] = merged_df['Candidates_PhoneNumber'].fillna(merged_df['Header_Phone'])

        merged_df.rename(columns={'Header_Emails': 'Candidates_Emails'}, inplace=True)

        merged_df = merged_df[['Filename', 'Candidates_Name', 'Name_from_File', 'Header_Name', 'Candidates_Emails', 'Candidates_PhoneNumber', 'PhoneNumbers_List']]
        
        return merged_df

    def save_to_s3(self, merged_df):
        """Saves the merged DataFrame to S3 as a CSV file."""
        if merged_df.empty:
            print("⚠ Warning: No data to save. Skipping file upload.")
            return

        try:
            csv_buffer = io.StringIO()
            merged_df.to_csv(csv_buffer, index=False)

            # Upload to S3
            s3_client.put_object(Bucket=BUCKET_NAME, Key=self.s3_output_key, Body=csv_buffer.getvalue())
            print(f"Merged data saved to S3: s3://{BUCKET_NAME}/{self.s3_output_key}")

        except NoCredentialsError:
            print("Error: AWS Credentials not found.")
        except Exception as e:
            print(f"Error saving merged data to S3: {e}")

    def process_data(self):
        """Executes the data processing pipeline."""
        self.clean_and_prepare_data()
        merged_df = self.merge_dataframes()
        self.save_to_s3(merged_df)

# Example usage
if __name__ == "__main__":
    s3_phone_numbers_key = "Function/phone_numbers.csv"  # S3 path for phone numbers CSV
    s3_email_key = "Function/email.csv"  # S3 path for email CSV
    s3_name_key = "Function/Demo_overall_name.csv"  # S3 path for name CSV
    s3_output_key = "Function/overall_Details.csv"  # S3 path for output CSV

    # Initialize DataMerger
    data_merger = DataMerger(s3_phone_numbers_key, s3_email_key, s3_name_key, s3_output_key)

    # Run data processing
    data_merger.process_data()

# import os
# import re
# import boto3
# import pandas as pd
# import io
# from botocore.exceptions import NoCredentialsError

# # AWS S3 Configuration
# AWS_ACCESS_KEY = "AKIAQ364P2C3AL25ZL7K"
# AWS_SECRET_KEY = "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"
# BUCKET_NAME = "texila-ai-resume"
# REGION_NAME = "ap-south-1"
# ENDPOINT_URL = "https://s3.ap-south-1.amazonaws.com"

# # Initialize S3 Client
# s3_client = boto3.client(
#     "s3",
#     aws_access_key_id=AWS_ACCESS_KEY,
#     aws_secret_access_key=AWS_SECRET_KEY,
#     region_name=REGION_NAME,
#     endpoint_url=ENDPOINT_URL
# )

# class ExperienceExtractor:
#     def __init__(self, s3_pdf_prefix, s3_output_key):
#         """
#         Initializes the ExperienceExtractor class.

#         Args:
#             s3_pdf_prefix (str): S3 prefix containing the PDF files.
#             s3_output_key (str): S3 key where extracted experience data will be saved.
#         """
#         self.s3_pdf_prefix = s3_pdf_prefix
#         self.s3_output_key = s3_output_key
#         self.experience_data = []

#     def extract_experience_from_filename(self, filename):
#         """
#         Extracts total experience from a filename using regex patterns.

#         Args:
#             filename (str): The name of the file from which to extract experience.

#         Returns:
#             tuple: A tuple of (years, months) representing total experience.
#         """
#         total_experience = None

#         # Pattern 1: Numbers before "year", "years", "yr", "yrs" or "m"
#         pattern_1 = r'(\d+(\.\d+)?)\s*(year|years|yr|yrs|m)'
#         match_1 = re.search(pattern_1, filename, re.IGNORECASE)

#         if match_1:
#             years = int(float(match_1.group(1)))  # Convert to int years
#             months = int((float(match_1.group(1)) - years) * 12)  # Convert decimal to months
#             total_experience = (years, months)

#         # Pattern 2: Numbers in square brackets like [10y_8m]
#         pattern_2 = r'\[(\d+)(y|yrs|yr?)?[_-](\d+)(m)?\]'
#         match_2 = re.search(pattern_2, filename)

#         if match_2:
#             years_in_bracket = int(match_2.group(1))
#             months_in_bracket = int(match_2.group(3))
#             total_experience = (years_in_bracket, months_in_bracket)

#         return total_experience

#     def process_files_in_s3(self):
#         """
#         Iterate through files in the S3 bucket and extract experience information.
#         """
#         try:
#             paginator = s3_client.get_paginator('list_objects_v2')
#             page_iterator = paginator.paginate(Bucket=BUCKET_NAME, Prefix=self.s3_pdf_prefix)

#             for page in page_iterator:
#                 for obj in page.get('Contents', []):
#                     key = obj['Key']
#                     filename = os.path.basename(key)

#                     if filename.lower().endswith(".pdf"):
#                         experience = self.extract_experience_from_filename(filename)
#                         if experience:
#                             self.experience_data.append([filename, f"{experience[0]} years, {experience[1]} months"])
        
#         except Exception as e:
#             print(f"Error processing PDF filenames from S3: {e}")

#     def save_experience_to_s3(self):
#         """
#         Save the extracted experience data to a CSV file in S3.
#         """
#         if not self.experience_data:
#             print("Warning: No experience data found. Skipping file upload.")
#             return

#         try:
#             df = pd.DataFrame(self.experience_data, columns=["Filename", "Total_Experience"])
#             csv_buffer = io.StringIO()
#             df.to_csv(csv_buffer, index=False)

#             # Upload to S3
#             s3_client.put_object(Bucket=BUCKET_NAME, Key=self.s3_output_key, Body=csv_buffer.getvalue())
#             print(f"Experience data saved to S3: s3://{BUCKET_NAME}/{self.s3_output_key}")

#         except NoCredentialsError:
#             print("Error: AWS Credentials not found.")
#         except Exception as e:
#             print(f"Error saving experience data to S3: {e}")

#     def extract_and_save(self):
#         """
#         Extract experience data from files in S3 and save it to S3.
#         """
#         self.process_files_in_s3()
#         self.save_experience_to_s3()

# # Example usage
# if __name__ == "__main__":
#     s3_pdf_prefix = "Function/processed_pdfs/"  # S3 folder containing resumes
#     s3_output_key = "Function/Fileexp_data.csv"  # Output file in S3

#     # Initialize ExperienceExtractor
#     experience_extractor = ExperienceExtractor(s3_pdf_prefix, s3_output_key)

#     # Extract experience from filenames and save
#     experience_extractor.extract_and_save()

import os
import re
import boto3
import io
import pandas as pd
import pdfplumber
from fuzzywuzzy import fuzz
from botocore.exceptions import NoCredentialsError

# AWS S3 Configuration
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

class PDFMatcher:
    def __init__(self, s3_pdf_prefix, s3_jd_prefix, s3_output_key):
        """
        Initializes the PDFMatcher class with S3 paths.

        Args:
            s3_pdf_prefix (str): S3 prefix for the folder containing PDF resumes.
            s3_jd_prefix (str): S3 prefix for the folder containing JD CSV files.
            s3_output_key (str): S3 key where the output CSV will be saved.
        """
        self.s3_pdf_prefix = s3_pdf_prefix
        self.s3_jd_prefix = s3_jd_prefix
        self.s3_output_key = s3_output_key
        self.results = []
        self.jd_csv_key = self.get_latest_csv_from_s3()

    def get_latest_csv_from_s3(self):
        """
        Fetches the latest JD CSV file from S3.
        """
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=BUCKET_NAME, Prefix=self.s3_jd_prefix)

            csv_files = [obj['Key'] for page in page_iterator for obj in page.get('Contents', []) if obj['Key'].endswith('.csv')]

            if not csv_files:
                print(f"Error: No JD CSV files found in S3 folder '{self.s3_jd_prefix}'.")
                return None

            latest_csv = max(csv_files, key=lambda key: s3_client.head_object(Bucket=BUCKET_NAME, Key=key)['LastModified'])
            print(f"Using JD CSV from S3: {latest_csv}")
            return latest_csv
        except Exception as e:
            print(f"Error fetching JD CSV from S3: {e}")
            return None

    def extract_text_from_pdf(self, file_bytes):
        """
        Extracts text from a PDF file.

        Args:
            file_bytes (bytes): The PDF file in bytes format.

        Returns:
            str: Extracted text from the PDF.
        """
        text = ""
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                for page in pdf.pages:
                    extracted_text = page.extract_text()
                    if extracted_text:
                        text += extracted_text
        except Exception as e:
            print(f"Error extracting text from PDF: {e}")
        return text.replace("Evaluation Warning: The document was created with Spire.Doc for Python.", "").strip()

    def calculate_match_percentage(self, text, search_word):
        """
        Calculates match percentage using fuzzy string matching.

        Args:
            text (str): Extracted resume text.
            search_word (str): Skill to search for.

        Returns:
            int: Match percentage (0-100).
        """
        return fuzz.partial_ratio(text.lower(), search_word.lower()) if text and search_word else 0

    def process_pdfs_and_find_matches(self):
        """
        Processes PDFs stored in S3 and finds matching words.
        """
        if not self.jd_csv_key:
            print("No valid JD CSV file found. Aborting process.")
            return pd.DataFrame()

        try:
            # Fetch JD CSV from S3
            jd_csv_obj = s3_client.get_object(Bucket=BUCKET_NAME, Key=self.jd_csv_key)
            jd_df = pd.read_csv(io.BytesIO(jd_csv_obj['Body'].read()))

            if 'Skills' not in jd_df.columns or 'Roles' not in jd_df.columns:
                print("Error: JD CSV missing required columns ('Skills', 'Roles').")
                return pd.DataFrame()

        except Exception as e:
            print(f"Error reading JD CSV from S3: {e}")
            return pd.DataFrame()

        # Fetch PDF files from S3
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=BUCKET_NAME, Prefix=self.s3_pdf_prefix)

            for page in page_iterator:
                for obj in page.get('Contents', []):
                    pdf_key = obj['Key']
                    if pdf_key.lower().endswith('.pdf'):
                        print(f"Processing resume: {pdf_key}")

                        # Fetch PDF file from S3
                        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=pdf_key)
                        file_bytes = response['Body'].read()

                        # Extract text from PDF
                        pdf_text = self.extract_text_from_pdf(file_bytes)

                        # Match against JD skills
                        for _, row in jd_df.iterrows():
                            search_word = str(row.get('Skills', '')).strip()
                            role = str(row.get('Roles', 'Unknown')).strip()

                            if search_word:
                                match_percentage = self.calculate_match_percentage(pdf_text, search_word)

                                if match_percentage > 50:  # Match threshold
                                    self.results.append({
                                        'Filename': os.path.basename(pdf_key),
                                        'Match Word': search_word,
                                        'Match Percentage': match_percentage,
                                        'Role': role
                                    })

        except Exception as e:
            print(f"Error processing PDFs from S3: {e}")

        results_df = pd.DataFrame(self.results)
        if not results_df.empty:
            self.save_results_to_s3(results_df)
            print(f"Matches found! Results saved to S3: s3://{BUCKET_NAME}/{self.s3_output_key}")
        else:
            print("No strong matches found.")

        return results_df

    def save_results_to_s3(self, results_df):
        """
        Saves the matched results to a CSV file in S3.
        """
        try:
            csv_buffer = io.StringIO()
            results_df.to_csv(csv_buffer, index=False)

            # Upload to S3
            s3_client.put_object(Bucket=BUCKET_NAME, Key=self.s3_output_key, Body=csv_buffer.getvalue())
        except NoCredentialsError:
            print("Error: AWS Credentials not found.")
        except Exception as e:
            print(f"Error saving results to S3: {e}")

# Example usage
if __name__ == "__main__":
    s3_pdf_prefix = "Function/processed_pdfs/"  # S3 folder containing resumes
    s3_jd_prefix = "Function/JD_uploads/"  # S3 folder containing JD CSVs
    s3_output_key = "Function/JD_Match.csv"  # Output file in S3

    # Initialize PDFMatcher
    pdf_matcher = PDFMatcher(s3_pdf_prefix, s3_jd_prefix, s3_output_key)

    # Process PDFs and find JD matches
    results_df = pdf_matcher.process_pdfs_and_find_matches()

    if not results_df.empty:
        print(results_df)


import os
import re
import boto3
import io
import pandas as pd
from glob import glob
from botocore.exceptions import NoCredentialsError

# AWS S3 Configuration
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

class ResumeJDMatcher:
    def __init__(self, s3_folder, s3_output_key):
        """
        Initializes the ResumeJDMatcher class with S3 paths.

        Args:
            s3_folder (str): S3 folder where input CSVs are stored.
            s3_output_key (str): S3 key where the merged output CSV will be saved.
        """
        self.s3_folder = s3_folder
        self.s3_output_key = s3_output_key
        self.details_csv_key = self.get_latest_file_from_s3("overall_Details")
        self.jd_match_csv_key = self.get_latest_file_from_s3("JD_Match")
        self.merged_df = None

    def get_latest_file_from_s3(self, keyword):
        """
        Fetches the latest CSV file from S3 that contains a given keyword.

        Args:
            keyword (str): Keyword to filter the required file.

        Returns:
            str: Latest CSV file key or None if not found.
        """
        try:
            paginator = s3_client.get_paginator('list_objects_v2')
            page_iterator = paginator.paginate(Bucket=BUCKET_NAME, Prefix=self.s3_folder)

            csv_files = [obj['Key'] for page in page_iterator for obj in page.get('Contents', []) if keyword in obj['Key'] and obj['Key'].endswith('.csv')]

            if not csv_files:
                print(f"No files found for '{keyword}' in S3 folder '{self.s3_folder}'.")
                return None

            latest_csv = max(csv_files, key=lambda key: s3_client.head_object(Bucket=BUCKET_NAME, Key=key)['LastModified'])
            print(f"Using latest {keyword} file from S3: {latest_csv}")
            return latest_csv
        except Exception as e:
            print(f"Error fetching {keyword} CSV from S3: {e}")
            return None

    def load_csv_from_s3(self, s3_key, label):
        """
        Loads a CSV file from S3 into a Pandas DataFrame.

        Args:
            s3_key (str): S3 key of the CSV file.
            label (str): Label for error messages.

        Returns:
            pd.DataFrame: Loaded DataFrame or an empty DataFrame if failed.
        """
        if not s3_key:
            print(f"Error: {label} file not found in S3.")
            return pd.DataFrame()

        try:
            response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
            df = pd.read_csv(io.BytesIO(response['Body'].read()))
            if df.empty:
                print(f"Warning: {label} CSV is empty.")
            return df
        except Exception as e:
            print(f"Error loading {label} CSV from S3: {e}")
            return pd.DataFrame()

    def merge_data(self):
        """
        Merges the `overall_Details` and `JD_Match` DataFrames on the `Filename` column.

        Returns:
            pd.DataFrame: Merged DataFrame or None if merging fails.
        """
        df1 = self.load_csv_from_s3(self.details_csv_key, "overall_Details")
        df2 = self.load_csv_from_s3(self.jd_match_csv_key, "JD_Match")

        if df1.empty or df2.empty:
            print("Error: One or both dataframes are empty. Cannot merge.")
            return None

        if "Filename" not in df1.columns or "Filename" not in df2.columns:
            print("Error: 'Filename' column missing in one of the DataFrames.")
            return None

        df1["Filename"] = df1["Filename"].astype(str).str.strip().str.lower()
        df2["Filename"] = df2["Filename"].astype(str).str.strip().str.lower()

        self.merged_df = pd.merge(df1, df2, on="Filename", how="left")
        print("DataFrames merged successfully. Sample output:")
        print(self.merged_df.head(2))
        return self.merged_df

    def save_results_to_s3(self):
        """
        Saves the merged DataFrame to a CSV file and uploads it to S3.
        """
        if self.merged_df is None or self.merged_df.empty:
            print("Error: No merged data to save.")
            return

        try:
            csv_buffer = io.StringIO()
            self.merged_df.to_csv(csv_buffer, index=False)

            # Upload to S3
            s3_client.put_object(Bucket=BUCKET_NAME, Key=self.s3_output_key, Body=csv_buffer.getvalue())
            print(f"Merged data saved to S3: s3://{BUCKET_NAME}/{self.s3_output_key}")
        except NoCredentialsError:
            print("Error: AWS Credentials not found.")
        except Exception as e:
            print(f"Error saving results to S3: {e}")

    def process_and_save(self):
        """
        Executes the full merging process and saves results to S3.
        """
        self.merge_data()
        self.save_results_to_s3()


# Example usage
if __name__ == "__main__":
    s3_folder = "Function/"  # S3 folder containing input CSVs
    s3_output_key = "Function/merged_output.csv"  # Output file in S3

    matcher = ResumeJDMatcher(s3_folder, s3_output_key)
    matcher.process_and_save()

import os
import boto3
import pandas as pd
import streamlit as st
import io
from botocore.exceptions import NoCredentialsError

# AWS S3 Configuration
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

# S3 Paths
TEMP_PDF_FOLDER = "Function/processed_pdfs/"
JD_UPLOAD_FOLDER = "Function/JD_uploads/"
MERGED_OUT_PATH = "Function/merged_output.csv"

# Cleanup Functions
def cleanup_s3_folder(s3_folder, file_type=None):
    """Deletes files from an S3 folder based on file type or deletes all files."""
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=BUCKET_NAME, Prefix=s3_folder)

        delete_keys = []
        for page in page_iterator:
            for obj in page.get('Contents', []):
                key = obj['Key']
                if file_type and not key.lower().endswith(file_type):
                    delete_keys.append({'Key': key})
                elif not file_type:
                    delete_keys.append({'Key': key})

        if delete_keys:
            s3_client.delete_objects(Bucket=BUCKET_NAME, Delete={'Objects': delete_keys})
            st.sidebar.success(f"{len(delete_keys)} files deleted from {s3_folder}!")
        else:
            st.sidebar.warning(f"No files found in {s3_folder} matching the criteria.")
    except NoCredentialsError:
        st.sidebar.error("AWS Credentials not found.")
    except Exception as e:
        st.sidebar.error(f"❌ Error deleting files: {e}")

# Sidebar navigation and buttons
st.sidebar.title("📂 File Management")
st.sidebar.button("Clear Non-PDF Files", on_click=lambda: cleanup_s3_folder(TEMP_PDF_FOLDER, file_type=".pdf"))
st.sidebar.button("Clear All PDFs", on_click=lambda: cleanup_s3_folder(TEMP_PDF_FOLDER))
st.sidebar.button("Clear All JD Uploads", on_click=lambda: cleanup_s3_folder(JD_UPLOAD_FOLDER))

# Load merged_output.csv from S3
def load_csv_from_s3(s3_key):
    """Loads a CSV file from S3 into a Pandas DataFrame."""
    try:
        response = s3_client.get_object(Bucket=BUCKET_NAME, Key=s3_key)
        df = pd.read_csv(io.BytesIO(response['Body'].read()))
        return df
    except s3_client.exceptions.NoSuchKey:
        st.warning("Merged_out.csv not found in S3. Please ensure the file is generated.")
        return None
    except Exception as e:
        st.error(f"Error loading CSV from S3: {e}")
        return None

# Display merged_output.csv if available
merged_df = load_csv_from_s3(MERGED_OUT_PATH)

if merged_df is not None:
    st.header("Merged Job Description & Resume Data")
    st.dataframe(merged_df)  # Interactive table

    # Convert DataFrame to CSV format for download
    merged_csv = merged_df.to_csv(index=False).encode("utf-8")

    # Buttons for View and Download
    st.download_button(
        label="Download Merged Data",
        data=merged_csv,
        file_name="Merged_out.csv",
        mime="text/csv"
    )













