.PHONY: dev build compose-up compose-down ingest local-up local-down local-bootstrap local-deploy local-test

dev:
	cd frontend && npm run dev

build:
	docker compose -f docker/docker-compose.yml build

compose-up:
	docker compose -f docker/docker-compose.yml up --build

compose-down:
	docker compose -f docker/docker-compose.yml down

ingest:
	# Requires a valid session cookie from an admin user.
	# Log in via the UI, copy the session cookie, then run:
	#   make ingest SESSION_COOKIE=<value>
	curl -X POST http://localhost:8000/api/admin/ingest \
		-H "Cookie: session=$${SESSION_COOKIE}"

local-up:
	docker compose -f infra/local/docker-compose.localstack.yml up -d

local-down:
	docker compose -f infra/local/docker-compose.localstack.yml down -v

local-bootstrap:
	bash infra/local/bootstrap.sh

local-deploy:
	cd infra && npx cdklocal deploy --all --require-approval never

local-test:
	cd backend && AWS_ENDPOINT_URL=http://localhost:4566 python3 -m pytest tests/integration -m integration -q
