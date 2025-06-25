#!/usr/bin/env python3
import argparse
import boto3
import os
import sys

def upload_file(s3, local_path: str, bucket: str, key_prefix: str):
    filename = os.path.basename(local_path)
    key = f"{key_prefix}/{filename}"
    print(f"Uploading {local_path} → s3://{bucket}/{key}")
    s3.upload_file(local_path, bucket, key)
    print("✔ done")

def main():
    parser = argparse.ArgumentParser(
        description="Upload a glTF asset (either .glb or .gltf+.bin) to S3"
    )
    parser.add_argument(
        "--bucket-output-name", "-b",
        help="The CloudFormation Output name for the bucket (e.g. GltfBucketName)",
        required=True
    )
    args = parser.parse_args()

    # discover your bucket name from CFN output
    cf = boto3.client("cloudformation")
    stacks = cf.describe_stacks(StackName="ProjectCodeStack")["Stacks"]
    outputs = stacks[0]["Outputs"]
    bucket = next(o["OutputValue"] for o in outputs
                  if o["OutputKey"] == args.bucket_output_name)

    s3 = boto3.client("s3")

    choice = input("Do you want to upload a single .glb or a .gltf+.bin pair? [glb/gltf]: ").strip().lower()
    if choice == "glb":
        glb_path = input("Path to your .glb file: ").strip()
        if not os.path.isfile(glb_path) or not glb_path.lower().endswith(".glb"):
            print("❌ Please provide a valid .glb file path.")
            sys.exit(1)
        upload_file(s3, glb_path, bucket, "")

    elif choice == "gltf":
        gltf_path = input("Path to your .gltf file: ").strip()
        bin_path  = input("Path to the accompanying .bin file: ").strip()
        for p, ext in [(gltf_path, ".gltf"), (bin_path, ".bin")]:
            if not os.path.isfile(p) or not p.lower().endswith(ext):
                print(f"❌ {p} is not a valid {ext} file.")
                sys.exit(1)
        # upload both side by side so Lambda sees them together
        upload_file(s3, gltf_path, bucket, "")
        upload_file(s3, bin_path,  bucket, "")

    else:
        print("❌ Invalid choice. Please run again and enter 'glb' or 'gltf'.")
        sys.exit(1)

    print("All done! Your files are in S3 and will trigger the parser Lambda.")

if __name__ == "__main__":
    main()

