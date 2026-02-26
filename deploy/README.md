# Deploy

This folder contains scripts intended to run on your production EC2 host.

## One-time EC2 setup

- Install Docker + Docker Compose.
- Clone this repo on the instance (example: `/opt/life-dashboard`).
- Create a production `.env` at the repo root (it is gitignored).
- Make sure the deploy user can:
  - talk to the Docker daemon (either in the `docker` group or has passwordless sudo for docker)
  - `git fetch` from `origin` without prompts (GitHub deploy key recommended)

## Deploy script

`deploy/deploy_prod.sh` does:

- `git fetch --prune origin`
- `git reset --hard origin/main` (branch/remote configurable)
- `docker compose --env-file .env -f docker/docker-compose.prod.yml up -d --build`

Environment variables:

- `DEPLOY_REMOTE` (default: `origin`)
- `DEPLOY_BRANCH` (default: `main`)
- `DEPLOY_PRUNE_IMAGES` (default: `1`)

## Important note about `.env` with Compose

`docker compose` loads `.env` from the "project directory" (which is often the directory containing the
compose file). Because the prod compose file lives in `docker/`, you can otherwise end up with compose
warnings like `The "POSTGRES_USER" variable is not set` even if the repo root has a valid `.env`.

`deploy/deploy_prod.sh` avoids this by passing `--env-file <repo_root>/.env` explicitly.

## GitHub Actions → SSM (recommended)

This repo includes a GitHub Actions workflow at `.github/workflows/deploy-prod.yml` that runs the deploy
script on your EC2 instance via AWS Systems Manager (SSM) Run Command.

### AWS setup (one-time)

1. Ensure your EC2 instance shows up in Systems Manager (Fleet Manager / Managed instances).
   - Install the SSM Agent (often preinstalled).
   - Attach an instance profile with `AmazonSSMManagedInstanceCore`.
2. Configure GitHub OIDC in IAM and create a role that GitHub Actions can assume.
3. Attach a policy to that role that can:
   - `ssm:SendCommand`, `ssm:GetCommandInvocation`
   - `ec2:DescribeInstances` (optional but commonly needed)

### GitHub repo secrets (required)

Add these repository secrets:

- `AWS_DEPLOY_ROLE_ARN` (IAM role to assume from Actions)
- `AWS_REGION`
- `EC2_INSTANCE_ID`

Optional:

- `EC2_USER` (default: `ec2-user`)
- `EC2_WORKDIR` (default: `/opt/life-dashboard`)

### EC2 repo access

The deploy script runs `git fetch/reset`, so the deploy user on the instance needs non-interactive Git access.
For GitHub, a read-only Deploy Key on the repo is the simplest approach.
