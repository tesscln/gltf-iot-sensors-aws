import sys
import time
import boto3
from botocore.exceptions import ClientError

CFN_STACK_NAME = "ProjectCodeStack"
CFN_OUTPUT_KEY  = "GltfBucketName"

# boto3 clients
cfn      = boto3.client("cloudformation")
s3       = boto3.resource("s3")
sitewise = boto3.client("iotsitewise")

def get_bucket_name_from_stack(stack_name, output_key):
    resp = cfn.describe_stacks(StackName=stack_name)
    for o in resp["Stacks"][0].get("Outputs", []):
        if o["OutputKey"] == output_key:
            return o["OutputValue"]
    print(f"Could not find output '{output_key}' in stack '{stack_name}'")
    sys.exit(1)

def empty_s3_bucket(bucket_name):
    print(f"Emptying bucket s3://{bucket_name} …")
    bucket = s3.Bucket(bucket_name)
    bucket.objects.all().delete()
    print("Bucket emptied")

def list_asset_models():
    paginator = sitewise.get_paginator("list_asset_models")
    for page in paginator.paginate():
        for m in page["assetModelSummaries"]:
            yield m["id"], m["name"]

def list_assets_for_model(model_id):
    paginator = sitewise.get_paginator("list_assets")
    for page in paginator.paginate(assetModelId=model_id):
        for a in page["assetSummaries"]:
            yield a["id"], a["name"]

def delete_asset(asset_id, asset_name):
    print(f"Deleting Asset {asset_name} ({asset_id})")
    sitewise.delete_asset(assetId=asset_id)

def wait_for_model_active(model_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = sitewise.describe_asset_model(assetModelId=model_id)
        state = resp["assetModelStatus"]["state"]
        if state == "ACTIVE":
            return
        if state == "FAILED":
            raise RuntimeError(f"Model {model_id} failed to activate")
        time.sleep(1)
    print(f"Timeout waiting for model {model_id}; proceeding anyway")

def delete_asset_model(model_id, model_name):
    print(f"Deleting AssetModel {model_name} ({model_id})")
    try:
        sitewise.delete_asset_model(assetModelId=model_id)
    except ClientError as e:
        print("Delete failed, retrying after activation…")
        wait_for_model_active(model_id)
        sitewise.delete_asset_model(assetModelId=model_id)

def main():
    bucket = get_bucket_name_from_stack(CFN_STACK_NAME, CFN_OUTPUT_KEY)
    empty_s3_bucket(bucket)

    print("Scanning for SiteWise AssetModels")
    found = False
    for model_id, model_name in list_asset_models():
        if not model_name.endswith("_AssetModel"):
            continue
        found = True
        print(f"Found model {model_name} ({model_id})")
        # delete its assets
        for aid, aname in list_assets_for_model(model_id):
            delete_asset(aid, aname)
        # then delete the model
        delete_asset_model(model_id, model_name)

    if not found:
        print("No matching AssetModels found.")

    print("Cleanup complete.")

if __name__ == "__main__":
    main()
