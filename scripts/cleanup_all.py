#!/usr/bin/env python3
import os
import sys
import time
import boto3
from botocore.exceptions import ClientError

CFN_STACK_NAME = "ProjectCodeStack"
CFN_BUCKET_OUTPUT_KEY = "GltfBucketName"

cf        = boto3.client("cloudformation")
s3        = boto3.resource("s3")
sitewise  = boto3.client("iotsitewise")

def get_bucket_from_cfn(stack_name, output_key):
    try:
        stacks = cf.describe_stacks(StackName=stack_name)["Stacks"]
        for o in stacks[0].get("Outputs", []):
            if o["OutputKey"] == output_key:
                return o["OutputValue"]
    except ClientError as e:
        print("Error reading CloudFormation outputs:", e)
    sys.exit(1)

def list_models_with_suffix(suffix="_AssetModel"):
    models = []
    paginator = sitewise.get_paginator("list_asset_models")
    for page in paginator.paginate():
        for mdl in page["assetModelSummaries"]:
            name = mdl["name"]
            if name.endswith(suffix):
                models.append((mdl["id"], name[:-len(suffix)]))
    return models

def delete_assets_for_model(model_id):
    paginator = sitewise.get_paginator("list_assets")
    to_delete = []
    for page in paginator.paginate(assetModelId=model_id):
        for a in page["assetSummaries"]:
            to_delete.append(a["id"])
    for asset_id in to_delete:
        print(f"→ Deleting Asset {asset_id}")
        sitewise.delete_asset(assetId=asset_id)
    # wait until they’re all gone
    while True:
        resp = sitewise.list_assets(assetModelId=model_id, maxResults=1)
        if not resp.get("assetSummaries"):
            return
        print("   waiting for assets to vanish…")
        time.sleep(2)

def delete_model(model_id, model_name):
    print(f"Deleting AssetModel {model_name} ({model_id})")
    sitewise.delete_asset_model(assetModelId=model_id)
    # wait until the model disappears from list
    while True:
        ids = [m["id"] for m,_ in list_models_with_suffix()]
        if model_id not in ids:
            return
        print("   waiting for model to disappear…")
        time.sleep(2)

def empty_s3_bucket(bucket_name):
    bucket = s3.Bucket(bucket_name)
    print(f"Emptying S3 bucket {bucket_name}")
    bucket.objects.all().delete()

def main():
    bucket_name = get_bucket_from_cfn(CFN_STACK_NAME, CFN_BUCKET_OUTPUT_KEY)
    print(f"Cleaning up bucket: {bucket_name}")

    # 1) tear down all SiteWise models & assets
    models = list_models_with_suffix()
    if not models:
        print("No AssetModels found matching '*_AssetModel'")
    for model_id, prefix in models:
        delete_assets_for_model(model_id)
        delete_model(model_id, prefix + "_AssetModel")

    # 2) empty the upload bucket
    empty_s3_bucket(bucket_name)

    print("Cleanup complete.")

if __name__ == "__main__":
    main()