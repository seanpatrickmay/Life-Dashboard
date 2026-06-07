from __future__ import annotations

from typing import TYPE_CHECKING

import aws_cdk as cdk
import cdk_nag
from aws_cdk import (
    Duration,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
)
from aws_cdk.aws_apigatewayv2 import HttpApi
from aws_cdk.aws_apigatewayv2_integrations import HttpLambdaIntegration
from aws_cdk.aws_lambda_event_sources import SqsEventSource
from constructs import Construct

if TYPE_CHECKING:
    from stacks.foundation_stack import FoundationStack


class ComputeStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        foundation: "FoundationStack",
        env: cdk.Environment | None = None,
    ) -> None:
        super().__init__(scope, id, env=env)
        self.foundation = foundation

        # --- Shared env: non-secret config + backend selection flags ---
        # Secrets are NOT here — they live in app_secret (Secrets Manager) and are loaded
        # at cold-start via load_secrets_into_env() when LD_SECRETS=secretsmanager.
        # AWS_REGION is RESERVED and intentionally omitted; the runtime provides it.
        common_env = {
            "LD_RUNTIME": "aws",
            "LD_JOB_QUEUE": "sqs",
            "LD_BLOB_STORE": "s3",
            "LD_KV_STORE": "dynamodb",
            "LD_SECRETS": "secretsmanager",
            "LD_SECRETS_NAME": foundation.app_secret.secret_name,
            "LD_S3_ASSET_BUCKET": foundation.asset_bucket.bucket_name,
            "LD_SQS_QUEUE_URL": foundation.job_queue.queue_url,
            "LD_DDB_KV_TABLE": foundation.kv_table.table_name,
            # ADMIN_EMAIL and FRONTEND_URL are intentionally NOT here.
            # They are loaded from the Secrets Manager secret at cold-start via
            # load_secrets_into_env().  See docs/deploy-serverless.md Step 3.
        }

        # --- One image, four functions via per-function CMD override ---
        # Uses from_ecr to reference the single DockerImageAsset built by FoundationStack.
        # CDK resolves the ECR repository + tag at synth time; no second docker build.
        def _fn(scope_id: str, cmd: list[str], *, timeout: int, memory: int) -> _lambda.DockerImageFunction:
            return _lambda.DockerImageFunction(self, scope_id,
                code=_lambda.DockerImageCode.from_ecr(
                    foundation.image_asset.repository,
                    tag_or_digest=foundation.image_asset.image_tag,
                    cmd=cmd,
                ),
                architecture=_lambda.Architecture.ARM_64,
                timeout=Duration.seconds(timeout),
                memory_size=memory,
                environment=common_env,
            )

        self.api_fn = _fn("ApiFn",
            ["app.aws.api_handler.handler"],
            timeout=30, memory=512)

        garmin_fn = _fn("GarminFn",
            ["app.aws.scheduled_handler.garmin_ingest"],
            timeout=300, memory=1024)

        digest_fn = _fn("DigestFn",
            ["app.aws.scheduled_handler.rss_digest"],
            timeout=300, memory=512)

        worker_fn = _fn("WorkerFn",
            ["app.aws.worker_handler.handler"],
            timeout=900, memory=1024)

        # --- IAM grants (least privilege) ---
        foundation.asset_bucket.grant_read_write(self.api_fn)
        foundation.kv_table.grant_read_write_data(self.api_fn)
        foundation.job_queue.grant_send_messages(self.api_fn)
        foundation.app_secret.grant_read(self.api_fn)

        foundation.app_secret.grant_read(garmin_fn)
        foundation.kv_table.grant_read_write_data(garmin_fn)
        foundation.job_queue.grant_send_messages(garmin_fn)

        foundation.app_secret.grant_read(digest_fn)
        foundation.kv_table.grant_read_write_data(digest_fn)
        foundation.job_queue.grant_send_messages(digest_fn)

        foundation.app_secret.grant_read(worker_fn)
        foundation.kv_table.grant_read_write_data(worker_fn)
        foundation.asset_bucket.grant_read_write(worker_fn)
        foundation.job_queue.grant_consume_messages(worker_fn)

        # --- HTTP API (HTTP API v2) → api_fn ($default route) ---
        self.http_api = HttpApi(self, "HttpApi",
            default_integration=HttpLambdaIntegration("ApiDefault", self.api_fn))

        # --- EventBridge schedules ---
        events.Rule(self, "GarminDaily",
            schedule=events.Schedule.cron(minute="0", hour="9"),
            targets=[targets.LambdaFunction(garmin_fn)])  # daily 09:00 UTC

        events.Rule(self, "DigestEvery6h",
            schedule=events.Schedule.rate(Duration.hours(6)),
            targets=[targets.LambdaFunction(digest_fn)])

        # --- SQS event source with partial batch failure reporting ---
        worker_fn.add_event_source(SqsEventSource(foundation.job_queue,
            batch_size=10,
            report_batch_item_failures=True))

        # --- Outputs ---
        cdk.CfnOutput(self, "HttpApiUrl", value=self.http_api.url or "")
        cdk.CfnOutput(self, "ApiFnName", value=self.api_fn.function_name)
        cdk.CfnOutput(self, "GarminFnName", value=garmin_fn.function_name)
        cdk.CfnOutput(self, "DigestFnName", value=digest_fn.function_name)
        cdk.CfnOutput(self, "WorkerFnName", value=worker_fn.function_name)

        # --- cdk-nag suppressions ---

        # IAM4: AWSLambdaBasicExecutionRole is the standard CDK-attached managed policy for all
        # Lambda functions. It grants only CloudWatch Logs write access. Writing a custom policy
        # to replace it would grant identical permissions with no security benefit. Suppressed for
        # all four function roles.
        _iam4_lambda_reason = (
            "AWSLambdaBasicExecutionRole grants CloudWatch Logs write-only access. "
            "It is the minimal standard policy attached by CDK to every Lambda execution role. "
            "Replacing it with a customer-managed policy of identical scope adds no security value."
        )
        for fn_construct in [self.api_fn, garmin_fn, digest_fn, worker_fn]:
            cdk_nag.NagSuppressions.add_resource_suppressions(
                fn_construct,
                [cdk_nag.NagPackSuppression(
                    id="AwsSolutions-IAM4",
                    reason=_iam4_lambda_reason,
                    applies_to=["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"],
                )],
                apply_to_children=True,
            )

        # IAM5: Wildcard actions/resources in the CDK L2 grant_* policies.
        # CDK's grant_read_write(S3), grant_read_write_data(DynamoDB), grant_send/consume_messages(SQS),
        # and grant_read(SecretsManager) all emit wildcard sub-actions (e.g. s3:GetObject*)
        # scoped to the specific resource ARN. The Resource::<Bucket.Arn>/* wildcard covers all
        # object keys within a single named bucket — this is accepted least-privilege for object stores.
        _iam5_s3_reason = (
            "CDK L2 grant_read_write on a single named S3 bucket. Wildcard actions "
            "(s3:GetObject*, s3:DeleteObject*, etc.) and the Resource::<bucket>/* are "
            "scoped to that one bucket ARN; this is standard CDK least-privilege for S3."
        )
        for fn_construct in [self.api_fn, worker_fn]:
            cdk_nag.NagSuppressions.add_resource_suppressions(
                fn_construct,
                [cdk_nag.NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason=_iam5_s3_reason,
                    applies_to=[
                        "Action::s3:GetObject*",
                        "Action::s3:GetBucket*",
                        "Action::s3:List*",
                        "Action::s3:DeleteObject*",
                        "Action::s3:Abort*",
                        "Resource::<AssetBucket1D025086.Arn>/*",
                    ],
                )],
                apply_to_children=True,
            )

        # APIG4: The HTTP API has no authorization configured at the route level.
        # This is intentional: the FastAPI application itself implements JWT bearer authentication
        # on every protected endpoint. Authorization is enforced in-app, not at the API Gateway layer.
        cdk_nag.NagSuppressions.add_resource_suppressions(
            self.http_api,
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-APIG4",
                reason=(
                    "Authorization is implemented by the FastAPI application via JWT bearer tokens "
                    "on every protected endpoint. API Gateway-level authorization (IAM/Cognito/Lambda "
                    "authorizer) is redundant and not warranted for this single-user personal dashboard."
                ),
            )],
            apply_to_children=True,
        )

        # APIG1: HTTP API access logging disabled.
        # This is a single-user personal dashboard; Lambda CloudWatch Logs provide sufficient
        # observability. API Gateway access logs add cost without meaningful benefit here.
        cdk_nag.NagSuppressions.add_resource_suppressions(
            self.http_api,
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-APIG1",
                reason=(
                    "API Gateway access logging omitted for this single-user personal dashboard. "
                    "Lambda CloudWatch Logs capture all invocation details. Access logging is a "
                    "runbook hardening item."
                ),
            )],
            apply_to_children=True,
        )
