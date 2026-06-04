import aws_cdk as cdk
import cdk_nag
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
            encryption=sqs.QueueEncryption.SQS_MANAGED,
        )
        self.job_queue = sqs.Queue(self, "JobQueue",
            visibility_timeout=Duration.seconds(960),
            enforce_ssl=True,
            encryption=sqs.QueueEncryption.SQS_MANAGED,
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

        # --- cdk-nag suppressions ---
        cdk_nag.NagSuppressions.add_resource_suppressions(
            self.asset_bucket,
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-S1",
                reason=(
                    "Asset bucket access logging omitted for this single-user personal dashboard. "
                    "S3 request logs add storage cost and operational overhead with no meaningful "
                    "security benefit for a private presigned-URL bucket. Tracked as runbook hardening."
                ),
            )],
        )
        cdk_nag.NagSuppressions.add_resource_suppressions(
            self.frontend_bucket,
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-S1",
                reason=(
                    "Frontend bucket access logging omitted. This bucket is private (CloudFront OAI "
                    "only) and is a single-user static site; logging is a runbook hardening item, not "
                    "a security requirement for this deployment."
                ),
            )],
        )
        cdk_nag.NagSuppressions.add_resource_suppressions(
            self.kv_table,
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-DDB3",
                reason=(
                    "DynamoDB PITR disabled. This table is an ephemeral KV cache (rate-limit counters, "
                    "session tokens) with a TTL; all durable data lives in the Neon Postgres database. "
                    "Losing this table is a cold-cache event, not data loss. Runbook hardening."
                ),
            )],
        )
        cdk_nag.NagSuppressions.add_resource_suppressions(
            self.app_secret,
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-SMG4",
                reason=(
                    "Secret holds third-party API keys (OpenAI, Garmin) and a Neon Postgres URL; "
                    "there is no AWS-managed rotation Lambda for these credential types. "
                    "Rotation is a manual runbook step performed out-of-band. "
                    "Auto-rotation is not applicable here."
                ),
            )],
        )
