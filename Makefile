.PHONY: dev build compose-up compose-down ingest

dev:
	cd frontend && npm run dev

build:
	docker compose -f docker/docker-compose.yml build

compose-up:
	docker compose -f docker/docker-compose.yml up --build

compose-down:
	docker compose -f docker/docker-compose.yml down

ingest:
	curl -X POST http://localhost:8000/api/admin/ingest -H "X-Admin-Token: $${READINESS_ADMIN_TOKEN}"
