import os
import json
import tempfile
import boto3

# boto3 clients
s3       = boto3.client("s3")
sitewise = boto3.client("iotsitewise")

# environment variable
BUCKET = os.environ["BUCKET_NAME"]

def handler(event, context):
    """
    Triggered by S3 ObjectCreated on the glTF bucket.
    Downloads the glTF file, parses its JSON structure,
    then creates an IoT SiteWise asset model + assets
    mirroring the glTF node hierarchy.
    """
    # 1) extract S3 info from the event
    record = event["Records"][0]["s3"]
    bucket = record["bucket"]["name"]
    key    = record["object"]["key"]

    # 2) download into a temp file
    local_path = os.path.join(tempfile.gettempdir(), os.path.basename(key))
    s3.download_file(bucket, key, local_path)

    # 3) load the JSON
    with open(local_path, "r") as f:
        gltf = json.load(f)

    # 4) derive a base model name from the filename
    base = os.path.splitext(os.path.basename(key))[0]
    model_name = f"{base}_AssetModel"

    # 5) create an Asset Model in SiteWise
    #    (you could first check if one already exists)
    model_response = sitewise.create_asset_model(
        assetModelName=model_name,
        assetModelDescription=f"Auto-generated from {key}",
        propertyDefinitions=[{
            "name": "placeholder",
            "dataType": "STRING",
            "type": { "attribute": {} }
        }]
    )
    asset_model_id = model_response["assetModelId"]

    # 6) walk the glTF nodes and create SiteWise Assets
    node_list = gltf.get("nodes", [])
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
