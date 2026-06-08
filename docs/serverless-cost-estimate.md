# Serverless Cost Estimate — Single User, Low Traffic

Estimates for a single-user personal dashboard with the following usage profile:
- ~200 API requests/day (browsing the dashboard, loading data)
- 2 scheduled Lambda invocations/day (Garmin ingest + RSS digest × 4/day = ~10/day)
- ~10 background job invocations/day via SQS worker
- ~1 GB/month CloudFront data transfer
- ~100 MB frontend static assets (S3)
- ~50 MB workspace asset uploads (S3)
- DB migrations: ~5 minutes/month of Fargate compute

All estimates use **us-east-1** pricing as of 2026. Prices may change; always verify
against the [AWS pricing pages](https://aws.amazon.com/pricing/).

---

## Per-Service Breakdown

### Lambda

**Pricing:** $0.20 per 1M requests + $0.0000133334 per GB-second (arm64 Graviton is
~20% cheaper than x86_64).

| Function | Invocations/mo | Avg duration | Memory | GB-seconds/mo |
|---|---|---|---|---|
| API (ApiFn, 512 MB) | ~6,000 | 300 ms | 512 MB | ~900 |
| Garmin (GarminFn, 1024 MB) | ~30 | 30 s | 1024 MB | ~900 |
| Digest (DigestFn, 512 MB) | ~120 | 20 s | 512 MB | ~1,200 |
| Worker (WorkerFn, 1024 MB) | ~300 | 5 s | 1024 MB | ~1,500 |

Total invocations: ~6,450/mo → well within free tier (1M/mo).
Total GB-seconds: ~4,500/mo → well within free tier (400,000 GB-s/mo).

**Lambda cost: ~$0.00/mo** (free tier covers it comfortably).

### API Gateway HTTP API

**Pricing:** $1.00 per 1M requests.

~6,000 requests/month → $0.006/mo.

**API Gateway cost: ~$0.01/mo**

### CloudFront

**Free tier:** 1 TB data transfer + 10M requests/mo (forever, not just first year).

~1 GB transfer, ~200,000 requests/mo → entirely within free tier.

**CloudFront cost: ~$0.00/mo**

### S3

**Pricing:** $0.023/GB/mo storage, $0.005 per 1,000 PUT requests, $0.0004 per 1,000 GET.

- Frontend assets: ~100 MB = ~$0.002/mo storage
- Workspace uploads: ~50 MB = ~$0.001/mo storage
- PUT/GET requests: negligible

**S3 cost: ~$0.01/mo**

### DynamoDB (on-demand)

**Pricing:** $1.25 per million write request units (WRU), $0.25 per million read request
units (RRU).

The KV table holds metrics cache (5 min TTL), auth rate-limit counters, and session data.
At ~200 API requests/day:
- ~1,000 WRU/day, ~5,000 RRU/day → ~30,000 WRU/mo, ~150,000 RRU/mo

**Free tier:** 25 WCU/RCU perpetually (on-demand does not use this free tier, but
requests are so low they stay well under $0.01/mo).

**DynamoDB cost: ~$0.04/mo**

### SQS

**Free tier:** 1M requests/mo (forever).

~10,000 messages/month → entirely within free tier.

**SQS cost: ~$0.00/mo**

### Secrets Manager

**Pricing:** $0.40 per secret per month + $0.05 per 10,000 API calls.

1 secret (`life-dashboard/app`) × $0.40 = $0.40/mo.
API calls (cold-start reads): ~100/mo = negligible.

**Secrets Manager cost: ~$0.40/mo**

### ECS Fargate (migrations only)

**Pricing:** $0.04048/vCPU-hour + $0.004445/GB-hour.

The migrate task runs 0.5 vCPU + 1 GB RAM, ~2 minutes per deploy.
Assuming 5 deploys/month: 5 × (2/60) hours = 0.167 hours.

- vCPU: 0.167 × 0.5 × $0.04048 = $0.003
- Memory: 0.167 × 1 × $0.004445 = $0.001

**Fargate cost: ~$0.01/mo**

### ECR

**Pricing:** $0.10/GB/mo after 500 MB free.

Image size ~1.47 GB → ~1 GB billable × $0.10 = $0.10/mo.

**ECR cost: ~$0.10/mo**

### CloudWatch Logs

**Pricing:** $0.50/GB ingested, $0.03/GB stored.

Lambda/ECS logs for low-traffic single-user: ~50 MB/mo ingested.
= $0.025 ingested + negligible storage.

**CloudWatch cost: ~$0.03/mo**

---

## Total Monthly Estimate

| Service | Est. monthly cost |
|---|---|
| Lambda | $0.00 (free tier) |
| API Gateway HTTP API | $0.01 |
| CloudFront | $0.00 (free tier) |
| S3 | $0.01 |
| DynamoDB | $0.04 |
| SQS | $0.00 (free tier) |
| Secrets Manager | $0.40 |
| ECS Fargate (migrations) | $0.01 |
| ECR | $0.10 |
| CloudWatch Logs | $0.03 |
| **Total** | **~$0.60/mo** |

Realistic range accounting for estimate uncertainty: **$0.50–$2.00/mo**.

---

## Comparison to Prior EC2 Architecture

| Architecture | Monthly cost | Notes |
|---|---|---|
| EC2 t3.micro (previous) | ~$8–12/mo | Always-on instance; EBS storage; data transfer |
| EC2 t3.small (if needed) | ~$15–20/mo | Higher for active use |
| **Serverless (this migration)** | **~$0.60–2.00/mo** | Pay-per-use; scales to zero |

**Estimated saving: ~$10/mo (~80–90% reduction).**

The biggest driver of savings is **no NAT Gateway** (which would cost $32/mo alone for
a VPC-attached Lambda setup) and **no always-on compute**. Lambda functions scale to zero
between invocations.

---

## Key Architectural Cost Drivers

- **No NAT Gateway:** Lambda functions run outside a VPC and connect to Neon over the
  public internet with TLS. This is the single largest serverless cost avoidance item
  (~$32/mo for a managed NAT).
- **No VPC for Lambda:** reduces cold-start latency and eliminates ENI provisioning cost.
- **ARM64/Graviton:** ~20% cheaper Lambda compute vs. x86_64 at identical performance
  for this Python workload.
- **Fargate only for migrations:** the migrate task runs for ~2 minutes per deploy, not
  continuously. No always-on ECS service.
- **Free tier longevity:** Lambda, CloudFront, and SQS free tiers are perpetual — not
  just the first 12 months.

---

## What Is Not Included

- **Neon Postgres:** existing subscription; cost unchanged by this migration.
- **Domain / Route 53:** optional; ~$0.50/mo for a hosted zone if using a custom domain.
- **WAF, flow logs, access logging:** noted as runbook hardening items; adding them would
  increase cost modestly (~$1–5/mo depending on rules).
- **Multi-region or blue/green:** out of scope for this single-user deployment.

---

## Disclaimer

These are estimates based on AWS public pricing as of 2026-06-04 and the usage profile
described above. Actual costs depend on exact request volumes, data transfer, retention
settings, and AWS pricing changes. Review your AWS Cost Explorer monthly and set a billing
alert to catch unexpected spikes.
