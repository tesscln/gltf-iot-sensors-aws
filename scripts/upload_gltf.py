#!/usr/bin/env python3
import sys
import os
import boto3
import botocore
import argparse

def main():
    parser = argparse.ArgumentParser(
        description="Upload a .gltf or .glb file to the S3 bucket created by CDK"
    )
    parser.add_argument(
        "--bucket",
        required=True,
        help="The name of the S3 bucket (from CloudFormation/CDK output)"
    )
    parser.add_argument(
        "--file",
        required=True,
        help="Path to the .gltf/.glb file on your local machine"
    )
    args = parser.parse_args()

    bucket_name = args.bucket
    file_path   = args.file

    if not os.path.isfile(file_path):
        print(f"Error: file not found at {file_path}")
        sys.exit(1)

    key = os.path.basename(file_path)
    s3 = boto3.client("s3")

    try:
        print(f"Uploading {file_path} → s3://{bucket_name}/{key} …")
        s3.upload_file(file_path, bucket_name, key)
        print("✓ Upload complete")
    except botocore.exceptions.ClientError as e:
        print("Failed to upload:", e)
        sys.exit(1)

    # Optionally print the object URL
    region = boto3.session.Session().region_name
    url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{key}"
    print(f"File is now available at: {url}")

if __name__ == "__main__":
    main()
