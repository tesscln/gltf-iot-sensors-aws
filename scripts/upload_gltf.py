#!/usr/bin/env python3
import argparse
import os
import sys
import boto3

def upload_file(s3_client, path, bucket, prefix=""):
    key = os.path.join(prefix, os.path.basename(path))
    print(f"Uploading {path} to s3://{bucket}/{key}")
    s3_client.upload_file(path, bucket, key)
    print(f"Uploaded {key}")

def main():
    parser = argparse.ArgumentParser(
        description="Upload glTF assets (.glb or .gltf + .bin) to an S3 bucket"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--bucket-output-name", "-o",
        help="CloudFormation output key for the bucket"
    )
    group.add_argument(
        "--bucket", "--bucket-name", "-b",
        dest="bucket_name",
        help="Direct S3 bucket name to use"
    )
    args = parser.parse_args()

    if args.bucket_name:
        bucket = args.bucket_name
    else:
        cf = boto3.client("cloudformation")
        stacks = cf.describe_stacks(StackName="ProjectCodeStack")["Stacks"]
        outputs = stacks[0].get("Outputs", [])
        try:
            bucket = next(
                o["OutputValue"]
                for o in outputs
                if o["OutputKey"] == args.bucket_output_name
            )
        except StopIteration:
            print(f"No CloudFormation output named '{args.bucket_output_name}' found.")
            sys.exit(1)

    s3 = boto3.client("s3")

    mode = input("Upload mode? Enter 'glb' for .glb or 'gltf' for .gltf + .bin: ").strip().lower()
    if mode == "glb":
        glb_path = input("Path to .glb file: ").strip()
        if not os.path.isfile(glb_path) or not glb_path.lower().endswith(".glb"):
            print("Invalid .glb file path.")
            sys.exit(1)
        upload_file(s3, glb_path, bucket)

    elif mode == "gltf":
        gltf_path = input("Path to .gltf file: ").strip()
        bin_path  = input("Path to .bin file: ").strip()
        if not os.path.isfile(gltf_path) or not gltf_path.lower().endswith(".gltf"):
            print("Invalid .gltf file path.")
            sys.exit(1)
        if not os.path.isfile(bin_path) or not bin_path.lower().endswith(".bin"):
            print("Invalid .bin file path.")
            sys.exit(1)
        upload_file(s3, gltf_path, bucket)
        upload_file(s3, bin_path, bucket)

    else:
        print("Mode must be 'glb' or 'gltf'.")
        sys.exit(1)

    print("Upload complete. Lambda function will process the new assets.")

if __name__ == "__main__":
    main()
