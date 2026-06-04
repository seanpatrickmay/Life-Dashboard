# Serverless Rollback Guide

If the serverless deployment has a critical issue and you need to fail back to the EC2
docker-compose path, this document explains how.

---

## Option A — Fast Rollback: Redirect Traffic Away from CloudFront

If the EC2 instance is still running (or can be brought up quickly), the fastest rollback
is to point your DNS away from CloudFront and back to the EC2 instance's address.

1. **If using a custom domain with Route 53:**
   - Update the A/CNAME alias record for your domain to point back to the EC2 Elastic IP
     or ELB instead of the CloudFront distribution.
   - Propagation: typically seconds to minutes with Route 53.

2. **If using the raw CloudFront domain (`*.cloudfront.net`):**
   - The CloudFront domain is baked into bookmarks and the Google OAuth config.
   - In this case, bring the EC2 stack up and update your client/bookmarks to hit the
     EC2 address directly while you diagnose the issue.
   - Update Google OAuth redirect URIs to the EC2 URL if needed.

---

## Option B — Bring the EC2 Stack Back Up

The EC2 docker-compose path is **kept as a fallback** and is untouched by this migration.

```bash
# SSH into the EC2 instance
ssh ec2-user@<ec2-ip>

# Navigate to the repo
cd /opt/life-dashboard

# Pull latest main and start the stack
git pull origin main
docker compose --env-file .env -f docker/docker-compose.prod.yml up -d --build

# Verify health
curl -sf http://localhost/health
```

The `deploy/deploy_prod.sh` script can also be run directly on the EC2 instance:

```bash
bash /opt/life-dashboard/deploy/deploy_prod.sh
```

Or trigger it remotely via the existing GitHub Actions workflow `deploy-prod.yml`
(push to `main` or use `workflow_dispatch`).

---

## Database Compatibility

**The Neon Postgres database is shared between both deployment paths and is unaffected
by this migration.** No destructive schema changes were made:

- The `garmin_token` table (added in Phase 1.3) stores Garmin OAuth tokens that previously
  lived on the EC2 filesystem. The EC2 app reads tokens from the filesystem path
  (`/data/garmin`) and falls back gracefully if DB tokens are absent — so the EC2 path
  continues to work.
- The `job_run` table (added in Phase 1.9) is used by the Lambda path for durable
  throttle tracking. The EC2 app uses in-process state for the same purpose; the table
  is ignored by the EC2 path.
- All other tables and columns are identical to the pre-migration schema.
- All Alembic migrations are **additive and forward-only**. The EC2 app will encounter
  the two new tables as extra tables it doesn't manage — this is harmless.

---

## Tearing Down the Serverless Stacks

If you decide to permanently decommission the serverless infrastructure:

```bash
cd infra
source .venv/bin/activate

# Destroy in reverse dependency order (Edge + DataJobs first, Foundation last)
npx cdk destroy LifeDash-Edge
npx cdk destroy LifeDash-DataJobs
npx cdk destroy LifeDash-Compute
npx cdk destroy LifeDash-Foundation
```

**Important retention notes:**

- **Asset S3 bucket** (`AssetBucketName` output of `LifeDash-Foundation`) has
  `RemovalPolicy.RETAIN` — it will **not** be deleted by `cdk destroy`. This preserves
  any user-uploaded workspace assets. Delete it manually from the AWS Console or CLI
  if you want to fully clean up:
  ```bash
  BUCKET=$(aws cloudformation describe-stacks \
    --stack-name LifeDash-Foundation \
    --query "Stacks[0].Outputs[?OutputKey=='AssetBucketName'].OutputValue" \
    --output text)
  aws s3 rm "s3://${BUCKET}" --recursive
  aws s3api delete-bucket --bucket "$BUCKET"
  ```

- **Frontend S3 bucket** has `RemovalPolicy.DESTROY` with `auto_delete_objects=True` —
  it will be deleted (it only contains the built frontend bundle, which is reproducible).

- **The CDK bootstrap stack** (`CDKToolkit-lifedash`) is NOT deleted by `cdk destroy`.
  You can delete it manually from CloudFormation if desired, but it has no ongoing cost.

- **The Secrets Manager secret** is deleted by `cdk destroy LifeDash-Foundation`, but
  with the default 30-day recovery window. Force-delete if needed:
  ```bash
  aws secretsmanager delete-secret \
    --secret-id life-dashboard/app \
    --force-delete-without-recovery
  ```

- **Neon database:** unaffected. The `garmin_token` and `job_run` tables can be dropped
  manually after you're confident in the rollback, but they are harmless if left in place.

---

## Summary of What Is Safe

| Item | Rollback-safe? | Notes |
|---|---|---|
| EC2 docker-compose path | Yes | Untouched; `deploy_prod.sh` still works |
| Neon Postgres schema | Yes | No destructive changes; EC2 app ignores new tables |
| `garmin_token` table | Yes | EC2 app falls back to filesystem tokens |
| `job_run` table | Yes | EC2 app uses in-process state; table is ignored |
| Frontend S3 bucket | Yes | Contains only built assets; reproducible |
| Asset S3 bucket | Yes | RETAIN policy; user uploads preserved |
| GitHub Actions `deploy-prod.yml` | Yes | Not modified; still deploys to EC2 |
