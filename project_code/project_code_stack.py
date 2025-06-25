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
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create an S3 bucket for uploads
        gltf_bucket = s3.Bucket(
            self, "GltfUploadBucket",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Create a Lambda to parse the glTF file and call IoT SiteWise
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
            },
        )

        # Grant S3 and SiteWise permissions
        gltf_bucket.grant_read(parser)
        parser.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "iotsitewise:CreateAssetModel",
                "iotsitewise:CreateAsset",
                "iotsitewise:UpdateAsset",
                # add more if needed…
            ],
            resources=["*"],
        ))

        # Subscribe Lambda to new-objects in the bucket
        gltf_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(parser),
        )

        # Output the bucket name once
        CfnOutput(self, "GltfBucketName",
            value=gltf_bucket.bucket_name,
            description="S3 bucket for uploading glTF files",
        )