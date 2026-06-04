from __future__ import annotations

from pathlib import Path

import aws_cdk as cdk
import cdk_nag
from aws_cdk import (
    Duration,
    aws_cloudfront as cf,
    aws_cloudfront_origins as origins,
    aws_s3_deployment as s3deploy,
)
from constructs import Construct


class EdgeStack(cdk.Stack):
    def __init__(
        self,
        scope: Construct,
        id: str,
        *,
        foundation,
        compute,
        env: cdk.Environment | None = None,
    ) -> None:
        super().__init__(scope, id, env=env)

        # --- API Gateway origin ---
        # Strip the scheme from api_endpoint ("https://…") to get the bare host.
        # compute.http_api.api_endpoint → "https://{id}.execute-api.{region}.amazonaws.com"
        api_domain = cdk.Fn.select(2, cdk.Fn.split("/", compute.http_api.api_endpoint))
        api_origin = origins.HttpOrigin(
            api_domain,
            protocol_policy=cf.OriginProtocolPolicy.HTTPS_ONLY,
        )

        # --- CloudFront distribution ---
        # Default behavior: React SPA served from private S3 via OAI (S3Origin auto-creates OAI).
        # NOTE: OAC support (S3BucketOrigin.with_origin_access_control) arrives in aws-cdk-lib 2.156+.
        #       We use OAI via S3Origin for 2.150 compatibility. Migrate to OAC in Task 4.5 / runbook.
        distribution = cf.Distribution(
            self,
            "Distribution",
            default_root_object="index.html",
            default_behavior=cf.BehaviorOptions(
                origin=origins.S3Origin(foundation.frontend_bucket),
                viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
            ),
            additional_behaviors={
                "/api/*": cf.BehaviorOptions(
                    origin=api_origin,
                    viewer_protocol_policy=cf.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                    allowed_methods=cf.AllowedMethods.ALLOW_ALL,
                    cache_policy=cf.CachePolicy.CACHING_DISABLED,
                    # Exclude the Host header so API Gateway uses its own host, not the viewer's.
                    # ALL_VIEWER_EXCEPT_HOST_HEADER is present in 2.150; no fallback needed.
                    origin_request_policy=cf.OriginRequestPolicy.ALL_VIEWER_EXCEPT_HOST_HEADER,
                ),
            },
            error_responses=[
                # SPA fallback: S3 returns 403/404 for client-side routes → serve index.html.
                cf.ErrorResponse(
                    http_status=403,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
                cf.ErrorResponse(
                    http_status=404,
                    response_http_status=200,
                    response_page_path="/index.html",
                    ttl=Duration.seconds(0),
                ),
            ],
        )
        self.distribution = distribution

        # --- Frontend deployment ---
        # Use the real build artifact if it exists; otherwise inject a placeholder HTML so
        # synth/deploy succeeds before the frontend has been built (Phase 5).
        dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
        if dist_dir.exists() and any(dist_dir.iterdir()):
            source = s3deploy.Source.asset(str(dist_dir))
        else:
            source = s3deploy.Source.data(
                "index.html",
                "<!doctype html><html><body>"
                "<!-- placeholder; real build deployed in Phase 5 -->"
                "</body></html>",
            )

        s3deploy.BucketDeployment(
            self,
            "DeployFrontend",
            sources=[source],
            destination_bucket=foundation.frontend_bucket,
            distribution=distribution,
            distribution_paths=["/*"],
        )

        # --- Outputs ---
        cdk.CfnOutput(self, "DistributionDomain", value=distribution.distribution_domain_name)
        cdk.CfnOutput(
            self,
            "DistributionUrl",
            value=f"https://{distribution.distribution_domain_name}",
        )

        # --- cdk-nag suppressions ---

        # CFR1: Geo restriction not configured.
        # Single-user personal dashboard; no need to restrict by geography.
        # Runbook hardening item if a future deployment requires geo-fencing.
        cdk_nag.NagSuppressions.add_resource_suppressions(
            distribution,
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-CFR1",
                reason=(
                    "Geo restriction is not required. This is a single-user personal dashboard with "
                    "no geo-fencing requirements. Documented as optional runbook hardening."
                ),
            )],
        )

        # CFR2: WAF not associated with the CloudFront distribution.
        # Single-user personal dashboard with no public attack surface warranting WAF.
        # WAF is documented as optional runbook hardening.
        cdk_nag.NagSuppressions.add_resource_suppressions(
            distribution,
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-CFR2",
                reason=(
                    "WAF not warranted for a single-user personal dashboard with no public "
                    "attack surface. Documented as optional runbook hardening."
                ),
            )],
        )

        # CFR3: CloudFront access logging disabled.
        # Single-user dashboard; Lambda and API Gateway logs provide sufficient observability.
        # Access logging is a runbook hardening item.
        cdk_nag.NagSuppressions.add_resource_suppressions(
            distribution,
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-CFR3",
                reason=(
                    "CloudFront access logging omitted for this single-user personal dashboard. "
                    "Application-level observability is provided by Lambda CloudWatch Logs. "
                    "Runbook hardening item."
                ),
            )],
        )

        # CFR4: Default CloudFront viewer certificate (TLS policy defaults to TLSv1).
        # Using the default CloudFront certificate (*.cloudfront.net) for the initial deployment.
        # A custom ACM certificate with TLS1.2_2021 minimum is a runbook step (requires a domain).
        cdk_nag.NagSuppressions.add_resource_suppressions(
            distribution,
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-CFR4",
                reason=(
                    "Using the default CloudFront certificate (*.cloudfront.net) for the initial "
                    "deployment. Upgrading to a custom ACM certificate with TLS1.2_2021 minimum "
                    "security policy requires a custom domain and is documented as a runbook step."
                ),
            )],
        )

        # CDK BucketDeployment auto-creates an IAM role and Lambda to copy assets.
        # IAM4 + IAM5 + L1 on the generated custom-resource Lambda are CDK framework internals —
        # not application code. Suppressed with apply_to_children=True to cover the role and Lambda.
        cdk_nag.NagSuppressions.add_resource_suppressions_by_path(
            self,
            "/LifeDash-Edge/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C/ServiceRole/Resource",
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-IAM4",
                reason=(
                    "CDK-managed BucketDeployment custom-resource Lambda role. "
                    "AWSLambdaBasicExecutionRole is auto-attached by the CDK framework; "
                    "this is not application code."
                ),
                applies_to=["Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"],
            )],
        )
        cdk_nag.NagSuppressions.add_resource_suppressions_by_path(
            self,
            "/LifeDash-Edge/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C/ServiceRole/DefaultPolicy/Resource",
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-IAM5",
                reason=(
                    "CDK-managed BucketDeployment custom-resource Lambda policy. "
                    "Wildcard actions (s3:GetObject*, s3:DeleteObject*, etc.) and the staging-bucket "
                    "Resource::* are generated by the CDK BucketDeployment L2 construct to copy "
                    "assets to the destination bucket. This is framework-managed code, not "
                    "application IAM."
                ),
                applies_to=[
                    "Action::s3:GetObject*",
                    "Action::s3:GetBucket*",
                    "Action::s3:List*",
                    "Action::s3:DeleteObject*",
                    "Action::s3:Abort*",
                    "Resource::arn:<AWS::Partition>:s3:::cdk-lifedash-assets-<AWS::AccountId>-us-east-1/*",
                    "Resource::<FrontendBucketEFE2E19C.Arn>/*",
                    "Resource::*",
                ],
            )],
        )
        cdk_nag.NagSuppressions.add_resource_suppressions_by_path(
            self,
            "/LifeDash-Edge/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C/Resource",
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-L1",
                reason=(
                    "CDK-managed BucketDeployment custom-resource Lambda. "
                    "The runtime version is controlled by the CDK framework, not application code. "
                    "Updating aws-cdk-lib will update this runtime."
                ),
            )],
        )
