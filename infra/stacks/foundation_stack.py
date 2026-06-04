import aws_cdk as cdk
from aws_cdk import (
    aws_s3 as s3,
    aws_dynamodb as ddb,
    aws_sqs as sqs,
    aws_secretsmanager as sm,
    aws_ecr_assets as ecr_assets,
    Duration,
    RemovalPolicy,
)
from constructs import Construct


class FoundationStack(cdk.Stack):
    def __init__(self, scope: Construct, id: str, *, env: cdk.Environment | None = None) -> None:
        super().__init__(scope, id, env=env)

        # --- Workspace asset bucket (user uploads; served via presigned GET) ---
        self.asset_bucket = s3.Bucket(self, "AssetBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.RETAIN,
            cors=[s3.CorsRule(
                allowed_methods=[s3.HttpMethods.GET],
                allowed_origins=["*"],
                allowed_headers=["*"],
            )],
        )

        # --- Frontend static bucket (private; served via CloudFront OAC in EdgeStack) ---
        self.frontend_bucket = s3.Bucket(self, "FrontendBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # --- Ephemeral KV (cache, rate-limit, etc.) with TTL ---
        self.kv_table = ddb.Table(self, "KvTable",
            partition_key=ddb.Attribute(name="pk", type=ddb.AttributeType.STRING),
            billing_mode=ddb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="expires_at",
            removal_policy=RemovalPolicy.DESTROY,
        )

        # --- Async job queue + DLQ ---
        self.job_dlq = sqs.Queue(self, "JobDlq",
            retention_period=Duration.days(14),
            enforce_ssl=True,
        )
        self.job_queue = sqs.Queue(self, "JobQueue",
            visibility_timeout=Duration.seconds(960),
            enforce_ssl=True,
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=5,
                queue=self.job_dlq,
            ),
        )

        # --- App secret (values populated out-of-band per runbook; created empty/template here) ---
        self.app_secret = sm.Secret(self, "AppSecret",
            secret_name="life-dashboard/app",
            description="Life Dashboard app secrets (DATABASE_URL, JWT, OpenAI, Garmin Fernet, OAuth). Populate via runbook.",
        )

        # --- Unified container image (one image, four entrypoints) ---
        self.image_asset = ecr_assets.DockerImageAsset(self, "AppImage",
            directory="../backend",
            file="Dockerfile.lambda",
            platform=ecr_assets.Platform.LINUX_ARM64,
        )

        # Outputs for visibility/runbook
        cdk.CfnOutput(self, "AssetBucketName", value=self.asset_bucket.bucket_name)
        cdk.CfnOutput(self, "FrontendBucketName", value=self.frontend_bucket.bucket_name)
        cdk.CfnOutput(self, "KvTableName", value=self.kv_table.table_name)
        cdk.CfnOutput(self, "JobQueueUrl", value=self.job_queue.queue_url)
        cdk.CfnOutput(self, "AppSecretArn", value=self.app_secret.secret_arn)
        cdk.CfnOutput(self, "ImageUri", value=self.image_asset.image_uri)
