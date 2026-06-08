# Life Dashboard — CDK Infrastructure

CDK Python app defining four stacks for the serverless migration.

## Install

```bash
# Python deps (isolated venv)
python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -r requirements.txt

# CDK CLI (project-local)
npm install
```

## Synthesize

```bash
cd infra
npx cdk synth
```

The `cdk.json` `app` field points to `.venv/bin/python3 app.py` so `aws-cdk-lib` is importable without activating the venv.

## Deploy to LocalStack

```bash
# Start LocalStack first, then:
cd infra
npx cdklocal bootstrap
npx cdklocal deploy --all
```

## Stacks

| Stack | Purpose |
|---|---|
| `LifeDash-Foundation` | VPC, shared IAM roles, parameter store |
| `LifeDash-Compute` | Lambda functions, API Gateway |
| `LifeDash-Edge` | CloudFront, S3 static hosting |
| `LifeDash-DataJobs` | EventBridge rules, Step Functions, ingestion Lambdas |

## Notes

- All stacks target `us-east-1`.
- `cdk.json` sets `bootstrapQualifier: lifedash` to avoid collisions with other CDK apps in the same account.
- `.venv/` and `node_modules/` are gitignored — run the install steps above after cloning.
