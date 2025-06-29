import os
import json
import tempfile
import time
import boto3
from botocore.exceptions import ClientError

s3      = boto3.client("s3")
sitewise = boto3.client("iotsitewise")
iot     = boto3.client("iot")

BUCKET    = os.environ["BUCKET_NAME"]
LAMBDA_ARN = os.environ["AWS_LAMBDA_FUNCTION_ARN"]

def find_asset_model_by_name(sitewise, name):
    paginator = sitewise.get_paginator("list_asset_models")
    for page in paginator.paginate():
        for m in page["assetModelSummaries"]:
            if m["name"] == name:
                return m["id"]
    return None

def wait_for_model_active(sitewise, mid, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        status = sitewise.describe_asset_model(assetModelId=mid)["assetModelStatus"]["state"]
        if status == "ACTIVE":
            return
        if status == "FAILED":
            raise RuntimeError(f"Model {mid} failed: {status}")
        time.sleep(1)
    raise TimeoutError(f"Timeout waiting for model {mid}")

def get_or_create_asset_model(sitewise, name, desc):
    mid = find_asset_model_by_name(sitewise, name)
    if mid:
        return mid
    resp = sitewise.create_asset_model(
        assetModelName=name,
        assetModelDescription=desc,
        assetModelProperties=[{
            "name": "placeholder",
            "dataType": "STRING",
            "type": {"attribute": {}}
        }]
    )
    mid = resp["assetModelId"]
    wait_for_model_active(sitewise, mid)
    return mid

def handler(event, context):
    record = event["Records"][0]["s3"]
    bucket = record["bucket"]["name"]
    key    = record["object"]["key"]

    # Only process .gltf/.glb
    if not key.lower().endswith((".gltf", ".glb")):
        return {"statusCode":200, "body":json.dumps({"skipped": key})}

    # Download main file
    local = os.path.join(tempfile.gettempdir(), os.path.basename(key))
    s3.download_file(bucket, key, local)

    # Optionally download .bin
    if key.lower().endswith(".gltf"):
        bin_key = key[:-5] + ".bin"
        try:
            s3.download_file(bucket, bin_key, local.replace(".gltf", ".bin"))
        except ClientError:
            pass

    with open(local, "r") as f:
        gltf = json.load(f)

    base       = os.path.splitext(os.path.basename(key))[0]
    model_name = f"{base}_AssetModel"
    mid        = get_or_create_asset_model(sitewise, model_name, f"From {key}")

    # Create one SiteWise Asset per glTF node
    for idx, node in enumerate(gltf.get("nodes", [])):
        node_name = node.get("name", f"Node{idx}")
        sitewise.create_asset(assetName=f"{base}_{node_name}", assetModelId=mid)

    # Build or update an IoT rule so every topic under "<base>/#" invokes this Lambda
    rule_name     = f"{base}_TopicRule"
    topic_pattern = f"{base}/#"
    sql           = f"SELECT topic(), * FROM '{topic_pattern}'"
    payload       = {
        "sql":             sql,
        "ruleDisabled":    False,
        "awsIotSqlVersion":"2016-03-23",
        "actions": [{
            "lambda": {"functionArn": LAMBDA_ARN}
        }]
    }

    # Delete old rule if exists
    try:
        iot.delete_topic_rule(ruleName=rule_name)
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceNotFoundException":
            raise

    iot.create_topic_rule(ruleName=rule_name, topicRulePayload=payload)

    return {"statusCode":200, "body":json.dumps({"model": mid, "rule": rule_name})}
