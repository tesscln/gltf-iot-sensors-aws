from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_lambda as _lambda,
    aws_s3_notifications as s3n,
    CfnOutput,
    aws_iam as iam,
    aws_logs as logs,
    RemovalPolicy,
    Duration,
)
from constructs import Construct
from pathlib import Path

class ProjectCodeStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create an S3 bucket for glTF file uploads
        self.gltf_bucket = s3.Bucket(
            self, "GltfUploadBucket",
            versioned=True,
            removal_policy=RemovalPolicy.DESTROY,  # DELETE for dev/testing, change to RETAIN in production
            auto_delete_objects=True  # DELETE for dev/testing
        )

        # Create a Lambda function
        self.gltf_parser_lambda = _lambda.Function(
            self, "GltfParserLambda",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="gltf_parser.handler",
            code=_lambda.Code.from_asset(
                str(Path(__file__).parent.joinpath("lambda"))
            ),
            timeout=Duration.minutes(5),
            memory_size=512,
            log_retention=logs.RetentionDays.ONE_WEEK,
            environment={
                "BUCKET_NAME": self.gltf_bucket.bucket_name,
            }
        )

        # Give Lambda permissions to read/write to S3 bucket
        self.gltf_bucket.grant_read_write(self.gltf_parser_lambda)

        # Grant IoT SiteWise permissions
        self.gltf_parser_lambda.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "iotsitewise:CreateAssetModel",
                "iotsitewise:CreateAsset",
                "iotsitewise:UpdateAsset",
                "iotsitewise:DescribeAsset",
                "iotsitewise:ListAssets",
                "iotsitewise:ListAssetModels",
            ],
            resources=["*"],
        ))

        # Trigger Lambda function once object is created in S3
        self.gltf_bucket.add_event_notification(
            s3.EventType.OBJECT_CREATED,
            s3n.LambdaDestination(self.gltf_parser_lambda)
        )

        # Output bucket name (to copy easily into upload script) in the Cfn terminal
        CfnOutput(self, "GltfBucketName",
                  value=self.gltf_bucket.bucket_name,
                  description="The name of the S3 bucket for uploading glTF files"
                  )
