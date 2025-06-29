from pathlib import Path

from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3_notifications as s3n,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_logs as logs,
    aws_lambda as lambda_,
    CfnOutput,
    RemovalPolicy,
    Duration,
)
from constructs import Construct

class ProjectCodeStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1) S3 bucket for glTF uploads
        gltf_bucket = s3.Bucket(
            self, "GltfUploadBucket",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # 2) Lambda function that will parse glTF and call SiteWise + IoT
        parser = _lambda.Function(
            self, "GltfParserLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="parse_gltf.handler",
            code=_lambda.Code.from_asset(str(Path(__file__).parent.joinpath("lambda"))),
            timeout=Duration.minutes(5),
            memory_size=512,
            log_retention=logs.RetentionDays.ONE_WEEK,
            environment={
                "BUCKET_NAME": gltf_bucket.bucket_name,
                # We'll also pass its own ARN so the function can build its IoT rule
                 "AWS_LAMBDA_FUNCTION_ARN": parser.function_arn
            }
        )

        # 3) Grant the Lambda read access to S3
        gltf_bucket.grant_read(parser)

        # 4) Grant the Lambda SiteWise and IoT permissions
        parser.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "iotsitewise:CreateAssetModel",
                "iotsitewise:DescribeAssetModel",
                "iotsitewise:ListAssetModels",
                "iotsitewise:CreateAsset",
                "iotsitewise:UpdateAsset",
                "iot:CreateTopicRule",
                "iot:DeleteTopicRule",
            ],
            resources=["*"],
        ))

        # 5) Explicitly allow IoT Core to invoke this Lambda (no SourceArn = no cycle)
        lambda_.CfnPermission(self, "AllowIoTInvoke",
            action="lambda:InvokeFunction",
            function_name=parser.function_name,
            principal="iot.amazonaws.com"
        )

        # 6) Wire up S3 → Lambda on object creation
        gltf_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(parser),
        )

        # 7) Export the bucket name for your upload script
        CfnOutput(self, "GltfBucketName",
            value=gltf_bucket.bucket_name,
            description="S3 bucket for uploading glTF files"
        )
