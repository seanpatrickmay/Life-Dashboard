# Setup Guide

1. Install Docker Desktop and ensure it is running.
2. Copy `.env.example` to `.env` and fill in `APP_ENV`, Google OAuth (local/prod), admin email, Garmin encryption key, and Vertex credentials.
   - To generate the Garmin encryption key: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
3. Set `FRONTEND_URL`, `GOOGLE_REDIRECT_URI_LOCAL`/`GOOGLE_REDIRECT_URI_PROD`, and `CORS_ORIGINS` for your environment.
4. Place the Garmin token cache under the path specified in `GARMIN_TOKENS_DIR` (defaults to `/data/garmin`, mounted via Docker volume).
5. Provide the Vertex AI service account JSON file at the path referenced by `VERTEX_SERVICE_ACCOUNT_JSON`.
6. Run `docker compose -f docker/docker-compose.yml up --build` to start the stack.
7. Visit the frontend on `http://localhost:4173` (prod build) or `http://localhost:5173` in dev mode, then sign in with Google.
