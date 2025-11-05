# Setup Guide

1. Install Docker Desktop and ensure it is running.
2. Copy `.env.example` to `.env` and fill in Garmin + Vertex credentials.
3. Place Garmin token cache under the path specified in `GARMIN_TOKENS_DIR` (defaults to `/data/garmin`, mounted via Docker volume).
4. Provide the Vertex AI service account JSON file at the path referenced by `VERTEX_SERVICE_ACCOUNT_JSON`.
5. Run `docker compose -f docker/docker-compose.yml up --build` to start the stack.
6. Visit the frontend on `http://localhost:4173` (prod build) or `http://localhost:5173` in dev mode.
