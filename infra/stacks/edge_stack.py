from __future__ import annotations

import aws_cdk as cdk
from constructs import Construct


class EdgeStack(cdk.Stack):
    def __init__(self, scope: Construct, id: str, *, foundation, compute, env: cdk.Environment | None = None) -> None:
        super().__init__(scope, id, env=env)
        self.foundation = foundation
        self.compute = compute
