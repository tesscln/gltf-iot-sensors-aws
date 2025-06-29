import argparse
import boto3
import time
import sys

sitewise = boto3.client("iotsitewise")
s3       = boto3.client("s3")

def list_assets_for_model(model_id):
    paginator = sitewise.get_paginator("list_assets")
    assets = []
    for page in paginator.paginate(assetModelId=model_id):
        assets += [a["id"] for a in page["assetSummaries"]]
    return assets

def delete_all_assets(model_id):
    # Gather all asset IDs
    assets = list_assets_for_model(model_id)
    if not assets:
        return

    print(f"Deleting {len(assets)} assets for model {model_id}")
    for asset_id in assets:
        print(f"– delete_asset({asset_id})")
        sitewise.delete_asset(assetId=asset_id)

    # 2) Wait until no assets remain
    deadline = time.time() + 60
    while time.time() < deadline:
        remaining = list_assets_for_model(model_id)
        if not remaining:
            print("All assets deleted")
            return
        print(f"   … waiting, {len(remaining)} still exist")
        time.sleep(3)

    print(" Timed out waiting for assets to delete")
    sys.exit(1)

def delete_asset_model(model_id, model_name):
    delete_all_assets(model_id)

    print(f"Deleting AssetModel {model_name} ({model_id})")
    try:
        sitewise.delete_asset_model(assetModelId=model_id)
        print("AssetModel deleted")
    except sitewise.exceptions.ConflictingOperationException as e:
        print("ConflictingOperationException, retrying in 5s …")
        time.sleep(5)
        sitewise.delete_asset_model(assetModelId=model_id)
        print("AssetModel deleted on retry")

def cleanup(bucket_name, model_prefix):
    print(f"Emptying S3 bucket {bucket_name}")
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket_name):
        for obj in page.get("Contents", []):
            print(f"  – delete_object {obj['Key']}")
            s3.delete_object(Bucket=bucket_name, Key=obj['Key'])
    print("S3 bucket emptied")

    paginator = sitewise.get_paginator("list_asset_models")
    for page in paginator.paginate():
        for model in page["assetModelSummaries"]:
            if model["name"].startswith(model_prefix):
                delete_asset_model(model["id"], model["name"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Clean up S3 + SiteWise assets & models for a given glTF prefix"
    )
    parser.add_argument("--bucket", "-b", help="S3 bucket name", required=True)
    parser.add_argument(
        "--model-prefix", "-p",
        help="Only delete AssetModels whose name starts with this",
        required=True
    )
    args = parser.parse_args()

    cleanup(args.bucket, args.model_prefix)