from __future__ import annotations

from typing import TYPE_CHECKING

import aws_cdk as cdk
from constructs import Construct

if TYPE_CHECKING:
    from stacks.foundation_stack import FoundationStack


class ComputeStack(cdk.Stack):
    def __init__(self, scope: Construct, id: str, *, foundation: "FoundationStack", env: cdk.Environment | None = None) -> None:
        super().__init__(scope, id, env=env)
        self.foundation = foundation
