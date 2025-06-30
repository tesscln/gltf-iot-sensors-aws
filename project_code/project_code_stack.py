from pathlib import Path

from aws_cdk import (
    Stack,
    Duration,
    RemovalPolicy,
    aws_s3               as s3,
    aws_s3_notifications as s3n,
    aws_lambda           as _lambda,
    aws_iam              as iam,
    aws_logs             as logs,
    CfnOutput,
)
from constructs import Construct

class ProjectCodeStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # 1) Bucket for glTF uploads
        bucket = s3.Bucket(self, "GltfUploadBucket",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # 2) Lambda that parses glTF and sets up the MQTT rule
        parser = _lambda.Function(self, "GltfParserLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="parse_gltf.handler",
            code=_lambda.Code.from_asset(str(Path(__file__).parent.joinpath("lambda"))),
            timeout=Duration.minutes(5),
            memory_size=512,
            log_retention=logs.RetentionDays.ONE_WEEK,
            environment={
                "BUCKET_NAME": bucket.bucket_name,
            }
        )

        # 3) S3 → Lambda permission
        bucket.grant_read(parser)

        # 4) Give the Lambda the API rights it needs
        parser.add_to_role_policy(iam.PolicyStatement(
            actions=[
                # SiteWise for asset-model creation
                "iotsitewise:CreateAssetModel",
                "iotsitewise:DescribeAssetModel",
                "iotsitewise:ListAssetModels",
                "iotsitewise:CreateAsset",
                "iotsitewise:ListAssets",
                # IoT Core to manage topic rules
                "iot:CreateTopicRule",
                "iot:DeleteTopicRule",
                # Lambda to allow it to grant invocation permission back to IoT Core
                "lambda:AddPermission",
            ],
            resources=["*"],
        ))

        # 5) Allow IoT Core to invoke *this* Lambda when the rule fires
        #    We’ll scope the SourceArn in code below, once we know the rule name.
        parser.add_permission("AllowIotInvoke",
            principal=iam.ServicePrincipal("iot.amazonaws.com"),
            action="lambda:InvokeFunction",
            # source_arn left broad here; the function code will lock it down
        )

        # 6) Hook up S3 → Lambda on new uploads
        bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(parser)
        )

        # 7) Export the bucket name for your upload script
        CfnOutput(self, "GltfUploadBucketName",
            value=bucket.bucket_name,
            description="Upload your .gltf/.glb files here"
        )
