from pathlib import Path

from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_logs as logs,
    CfnOutput,
    RemovalPolicy,
    Duration,
)
from constructs import Construct

class ProjectCodeStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # 1) S3 bucket for uploads
        gltf_bucket = s3.Bucket(
            self, "GltfUploadBucket",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # 2) The Lambda that will parse .gltf/.glb and call SiteWise/IoT
        gltfParserFn = _lambda.Function(
            self, "GltfParserLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="parse_gltf.handler",
            code=_lambda.Code.from_asset(str(Path(__file__).parent.joinpath("lambda"))),
            timeout=Duration.minutes(5),
            memory_size=512,
            log_retention=logs.RetentionDays.ONE_WEEK,
            environment={
                "BUCKET_NAME": gltf_bucket.bucket_name,
                # pass the function’s own ARN so the Lambda can set up its own IoT Rule
                "AWS_LAMBDA_FUNCTION_ARN": "<will be set below>",
            }
        )

        # Now that gltfParserFn exists, inject its ARN
        gltfParserFn.add_environment("AWS_LAMBDA_FUNCTION_ARN", gltfParserFn.function_arn)

        # 3) Permissions
        gltf_bucket.grant_read(gltfParserFn)
        gltfParserFn.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "iotsitewise:CreateAssetModel",
                "iotsitewise:CreateAsset",
                "iotsitewise:UpdateAsset",
                "iotsitewise:DescribeAssetModel",
                "iotsitewise:ListAssetModels",
                "iotsitewise:ListAssets",
                "iotsitewise:ListAssetProperties",
                "iotsitewise:ListAssetPropertyValues",
                "iotsitewise:ListAssetPropertyValueHistory",
                "iotsitewise:ListAssetPropertyAggregates",
                "iot:CreateTopicRule",
                "iot:DeleteTopicRule",
                "lambda:AddPermission",
            ],
            resources=["*"],
        ))

        # Allow IoT service to invoke this Lambda
        gltfParserFn.grant_invoke(iam.ServicePrincipal("iot.amazonaws.com"))

        # 4) Trigger on uploads
        gltf_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(gltfParserFn),
        )

        # 5) Export bucket name for upload scripts
        CfnOutput(self, "GltfBucketName",
                  value=gltf_bucket.bucket_name,
                  description="S3 bucket for uploading glTF files")
