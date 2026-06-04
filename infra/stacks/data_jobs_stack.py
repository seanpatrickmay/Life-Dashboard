from __future__ import annotations

import aws_cdk as cdk
import cdk_nag
from aws_cdk import (
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_logs as logs,
    RemovalPolicy,
)
from constructs import Construct


class DataJobsStack(cdk.Stack):
    def __init__(self, scope: Construct, id: str, *, foundation, env: cdk.Environment | None = None) -> None:
        super().__init__(scope, id, env=env)

        # Minimal VPC: public subnets only, NO NAT (Fargate task reaches Neon over the public internet
        # via a public IP; avoids NAT Gateway cost). Lambdas are VPC-less; only Fargate needs a VPC.
        vpc = ec2.Vpc(self, "JobsVpc",
            max_azs=2,
            nat_gateways=0,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                )
            ],
        )

        cluster = ecs.Cluster(self, "JobsCluster", vpc=vpc)

        task_def = ecs.FargateTaskDefinition(self, "MigrateTask",
            cpu=512,
            memory_limit_mib=1024,
            runtime_platform=ecs.RuntimePlatform(
                cpu_architecture=ecs.CpuArchitecture.ARM64,
                operating_system_family=ecs.OperatingSystemFamily.LINUX,
            ),
        )

        task_def.add_container("migrate",
            image=ecs.ContainerImage.from_docker_image_asset(foundation.image_asset),
            entry_point=["python"],
            command=["-m", "app.aws.migrate"],
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix="migrate",
                log_retention=logs.RetentionDays.ONE_MONTH,
            ),
            environment={
                "LD_RUNTIME": "aws",
                "LD_SECRETS": "secretsmanager",
                "LD_SECRETS_NAME": foundation.app_secret.secret_name,
                # NOTE: DATABASE_URL_MIGRATIONS, DATABASE_URL, FRONTEND_URL, ADMIN_EMAIL,
                # GARMIN_PASSWORD_ENCRYPTION_KEY are loaded from the secret JSON by
                # load_secrets_into_env() at the top of migrate.main(). The secret MUST include them.
            },
        )

        foundation.app_secret.grant_read(task_def.task_role)

        self.cluster = cluster
        self.migrate_task = task_def
        self.vpc = vpc

        # Outputs for the runbook (aws ecs run-task needs cluster, task def, subnets, security group)
        cdk.CfnOutput(self, "ClusterName", value=cluster.cluster_name)
        cdk.CfnOutput(self, "MigrateTaskDefArn", value=task_def.task_definition_arn)
        cdk.CfnOutput(self, "PublicSubnetIds",
            value=cdk.Fn.join(",", [s.subnet_id for s in vpc.public_subnets]))

        # --- cdk-nag suppressions ---

        # VPC7: No VPC Flow Logs configured.
        # This is an ephemeral VPC used exclusively for one-shot Fargate migration tasks.
        # There are no persistent workloads; flow logs would add ongoing cost with no operational
        # benefit. Documented as runbook hardening.
        cdk_nag.NagSuppressions.add_resource_suppressions(
            vpc,
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-VPC7",
                reason=(
                    "Ephemeral VPC used only for on-demand Fargate migration task runs (one-shot "
                    "DB schema migrations). No persistent workloads; VPC Flow Logs are a runbook "
                    "hardening item, not a requirement for this use case."
                ),
            )],
        )

        # ECS4: CloudWatch Container Insights disabled on the cluster.
        # Container Insights add cost; this cluster runs a single one-shot migration task.
        # CloudWatch Logs (already configured on the container) provide sufficient observability.
        cdk_nag.NagSuppressions.add_resource_suppressions(
            cluster,
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-ECS4",
                reason=(
                    "CloudWatch Container Insights disabled. The cluster runs a single one-shot "
                    "migration task; detailed container metrics are unnecessary overhead. "
                    "Structured logs via awslogs driver are already configured."
                ),
            )],
        )

        # ECS2: Task definition specifies environment variables directly.
        # The variables set here (LD_RUNTIME, LD_SECRETS, LD_SECRETS_NAME) are non-secret
        # deployment configuration, not credentials. All actual secrets (DATABASE_URL, API keys)
        # are loaded at runtime from Secrets Manager by load_secrets_into_env(). Injecting
        # non-secret config via SSM Parameter Store would add complexity with no security benefit.
        cdk_nag.NagSuppressions.add_resource_suppressions(
            task_def,
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-ECS2",
                reason=(
                    "Environment variables are non-secret deployment config flags "
                    "(LD_RUNTIME, LD_SECRETS, LD_SECRETS_NAME). No credentials are hardcoded. "
                    "All actual secrets are injected at runtime from Secrets Manager via "
                    "load_secrets_into_env()."
                ),
            )],
        )

        # IAM5: Wildcard Resource::* in the Fargate execution role's default policy.
        # CDK auto-generates an execution role for Fargate tasks that needs ECR pull access.
        # The Resource::* on ECR actions is standard CDK behavior for container image tasks;
        # it cannot reference a specific ECR repo ARN at synth time for cross-stack image assets.
        cdk_nag.NagSuppressions.add_resource_suppressions(
            task_def,
            [cdk_nag.NagPackSuppression(
                id="AwsSolutions-IAM5",
                reason=(
                    "CDK-generated Fargate task execution role policy. Resource::* on ECR pull "
                    "actions is standard CDK behavior for DockerImageAsset tasks; the ECR repo "
                    "ARN is not available at synth time for cross-stack image assets."
                ),
                applies_to=["Resource::*"],
            )],
            apply_to_children=True,
        )
