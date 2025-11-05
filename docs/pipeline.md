# Data & Insight Pipeline

1. **Garmin Ingestion**
   - Authenticates with cached tokens via `python-garminconnect`.
   - Pulls activities, HRV, resting HR, and sleep summaries.
   - Persists raw + normalized data into PostgreSQL.
2. **Metric Aggregation**
   - Daily job computes training load windows, HRV/RHR baselines, and sleep debt metrics.
3. **Vertex AI Readiness**
   - Summarizes recent metrics into a structured prompt.
   - Calls Vertex AI text generation model and stores the narrative & readiness score.
4. **API Delivery**
   - FastAPI exposes endpoints for time-series data and the newest readiness insight.
5. **Frontend Visualization**
   - React client fetches summaries, renders Monet-inspired charts, and highlights the daily insight.
