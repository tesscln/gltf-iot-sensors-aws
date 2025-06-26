import os
import json
import tempfile
import boto3
import time
from botocore.exceptions import ClientError

# boto3 clients
s3       = boto3.client("s3")
sitewise = boto3.client("iotsitewise")

# environment variable
BUCKET = os.environ["BUCKET_NAME"]

def find_asset_model_by_name(sitewise, name):
    """
    Returns the first assetModelId whose assetModelName matches `name`,
    or None if no such model exists.
    """
    paginator = sitewise.get_paginator("list_asset_models")
    for page in paginator.paginate():
        for model in page["assetModelSummaries"]:
            if model["name"] == name:
                return model["id"]
    return None

def get_or_create_asset_model(sitewise, name, description):
    # 1) Try to find an existing one
    model_id = find_asset_model_by_name(sitewise, name)
    if model_id:
        return model_id

    # 2) Not found: create a new one
    resp = sitewise.create_asset_model(
        assetModelName=name,
        assetModelDescription=description,
        assetModelProperties=[{
            "name": "placeholder",
            "dataType": "STRING",
            "type": { "attribute": {} }
        }]
    )
    model_id = resp["assetModelId"]

    # 3) Wait until it becomes ACTIVE (see earlier snippet)
    wait_for_model_active(sitewise, model_id)
    return model_id

def wait_for_model_active(sitewise, model_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = sitewise.describe_asset_model(assetModelId=model_id)
        state = resp["assetModelStatus"]["state"]
        if state == "ACTIVE":
            return True
        if state == "FAILED":
            raise RuntimeError(f"AssetModel {model_id} failed to activate: {resp['assetModelStatus']}")
        time.sleep(1)
    raise TimeoutError(f"Timed out waiting for AssetModel {model_id} to become ACTIVE")


def handler(event, context):
    """
    Triggered by S3 notification of objectCreated in the S3 glTF bucket.
    It downloads the glTF file, parses its JSON structure,
    then creates an IoT SiteWise asset model + assets
    corresponding to the glTF node hierarchy.
    """
    # Extract S3 info from the event
    record = event["Records"][0]["s3"]
    bucket = record["bucket"]["name"]
    key    = record["object"]["key"]

    # Only process .gltf and .glb files (ignore .bin files)
    if not key.lower().endswith(('.gltf', '.glb')):
        print(f"Ignoring non-glTF file: {key}")
        return {
            "statusCode": 200,
            "body": json.dumps({"message": f"Ignored non-glTF file: {key}"})
        }

    # Download the main glTF file into a temp file
    local_path = os.path.join(tempfile.gettempdir(), os.path.basename(key))
    s3.download_file(bucket, key, local_path)
    print(f"Downloaded {key} to {local_path}")

    # If this is a .gltf file, also download the corresponding .bin file
    if key.lower().endswith('.gltf'):
        bin_key = key.replace('.gltf', '.bin')
        bin_local_path = os.path.join(tempfile.gettempdir(), os.path.basename(bin_key))
        
        try:
            s3.download_file(bucket, bin_key, bin_local_path)
            print(f"Downloaded {bin_key} to {bin_local_path}")
        except Exception as e:
            print(f"Warning: Could not download {bin_key}: {e}")
            # Continue without .bin file - some .gltf files don't have external binaries

    # Load the JSON
    with open(local_path, "r") as f:
        gltf = json.load(f)

    # Derive an asset model name from the filename
    base = os.path.splitext(os.path.basename(key))[0]  # e.g. “turbine”
    model_name = f"{base}_AssetModel"
    model_id = get_or_create_asset_model(
    sitewise,
    name=model_name,
    description=f"Auto-generated from {key}"
)
    
    asset_model_id = model_id

    # Walk the glTF nodes and create SiteWise Assets
    node_list = gltf.get("nodes", [])
    print(f"Found {len(node_list)} nodes in glTF file:")
    for idx, node in enumerate(node_list):
        print(f"  Node {idx}: {node}")
    
    for idx, node in enumerate(node_list):
        node_name = node.get("name", f"Node{idx}")
        # create one asset per node
        asset_response = sitewise.create_asset(
            assetName=f"{base}_{node_name}",
            assetModelId=asset_model_id,
        )
        asset_id = asset_response["assetId"]

        # (optional) now you could map properties to IoT topics here

    return {
        "statusCode": 200,
        "body": json.dumps({
            "message": "glTF parsed and SiteWise assets created",
            "assetModelId": asset_model_id
        })
    }
