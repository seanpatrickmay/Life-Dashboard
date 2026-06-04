from __future__ import annotations

import aws_cdk as cdk
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
