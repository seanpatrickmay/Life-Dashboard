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
	# Requires a valid session cookie from an admin user.
	# Log in via the UI, copy the session cookie, then run:
	#   make ingest SESSION_COOKIE=<value>
	curl -X POST http://localhost:8000/api/admin/ingest \
		-H "Cookie: session=$${SESSION_COOKIE}"
