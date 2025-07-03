import os, json, tempfile, time, boto3
from botocore.exceptions import ClientError

s3         = boto3.client("s3")
sitewise   = boto3.client("iotsitewise")
iot        = boto3.client("iot")
sts        = boto3.client("sts")
lambda_cli = boto3.client("lambda")

BUCKET = os.environ["BUCKET_NAME"]


def find_model(name):
    for page in sitewise.get_paginator("list_asset_models").paginate():
        for m in page["assetModelSummaries"]:
            if m["name"] == name:
                return m["id"]
    return None


def wait_active(model_id, timeout=60):
    deadline = time.time() + timeout
    while time.time() < deadline:
        st = sitewise.describe_asset_model(assetModelId=model_id)["assetModelStatus"]["state"]
        if st == "ACTIVE":
            return
        if st == "FAILED":
            raise RuntimeError("Model failed activation")
        time.sleep(1)
    raise TimeoutError("Timed out waiting for model to activate")


def get_or_create_model(base, desc):
    name = f"{base}_AssetModel"
    existing = find_model(name)
    if existing:
        return existing
    resp = sitewise.create_asset_model(
        assetModelName=name,
        assetModelDescription=desc,
        assetModelProperties=[{
            "name": "placeholder",
            "dataType": "STRING",
            "type": {"attribute": {}}
        }]
    )
    wait_active(resp["assetModelId"])
    return resp["assetModelId"]


def handler(event, context):
    # 1) Download & parse glTF
    rec = event["Records"][0]["s3"]
    key = rec["object"]["key"]
    if not key.lower().endswith((".gltf", ".glb")):
        return {"statusCode":200,"body":"ignored"}

    local = os.path.join(tempfile.gettempdir(), os.path.basename(key))
    s3.download_file(BUCKET, key, local)
    gltf = json.load(open(local))

    base = os.path.splitext(os.path.basename(key))[0]

    # 2) Create SiteWise model & assets
    model_id = get_or_create_model(base, f"Auto from {key}")
    for idx, node in enumerate(gltf.get("nodes", [])):
        nm = node.get("name", f"Node{idx}")
        sitewise.create_asset(assetName=f"{base}_{nm}", assetModelId=model_id)

    # 3) Create IoT Topic Rule
    rule_name = f"{base}_TopicRule"
    topic     = f"{base}/#"
    sql_stmt  = f"SELECT topic() AS mqttTopic, * FROM '{topic}'"
    lambda_arn = context.invoked_function_arn

    account = sts.get_caller_identity()["Account"]
    region  = os.environ["AWS_REGION"]
    rule_arn = f"arn:aws:iot:{region}:{account}:rule/{rule_name}"

    # 3a) Grant IoT Core permission to invoke this Lambda
    try:
        lambda_cli.add_permission(
            FunctionName=lambda_arn,
            StatementId=f"{rule_name}-InvokePerm",
            Action="lambda:InvokeFunction",
            Principal="iot.amazonaws.com",
            SourceArn=rule_arn
        )
    except lambda_cli.exceptions.ResourceConflictException:
        pass  # already granted

    # 3b) Directly create (or overwrite) the rule
    iot.create_topic_rule(
        ruleName=rule_name,
        topicRulePayload={
            "sql":              sql_stmt,
            "ruleDisabled":     False,
            "awsIotSqlVersion": "2016-03-23",
            "actions": [
                {"lambda": {"functionArn": lambda_arn}}
            ]
        }
    )

    return {
        "statusCode": 200,
        "body": json.dumps({
            "model": model_id,
            "rule":  rule_name
        })
    }