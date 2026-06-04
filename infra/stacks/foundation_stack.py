import aws_cdk as cdk
from constructs import Construct


class FoundationStack(cdk.Stack):
    def __init__(self, scope: Construct, id: str, *, env: cdk.Environment | None = None) -> None:
        super().__init__(scope, id, env=env)
