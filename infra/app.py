#!/usr/bin/env python3
import aws_cdk as cdk
from stacks.foundation_stack import FoundationStack
from stacks.compute_stack import ComputeStack
from stacks.edge_stack import EdgeStack
from stacks.data_jobs_stack import DataJobsStack

app = cdk.App()
env = cdk.Environment(region="us-east-1")
foundation = FoundationStack(app, "LifeDash-Foundation", env=env)
compute = ComputeStack(app, "LifeDash-Compute", foundation=foundation, env=env)
EdgeStack(app, "LifeDash-Edge", foundation=foundation, compute=compute, env=env)
DataJobsStack(app, "LifeDash-DataJobs", foundation=foundation, env=env)
app.synth()
