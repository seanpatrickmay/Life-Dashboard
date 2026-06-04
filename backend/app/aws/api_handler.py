"""API Gateway (HTTP API v2) -> FastAPI via Mangum."""
from app.aws.bootstrap import cold_start
cold_start()                       # runs once at import (Lambda cold start)
from app.main import app           # noqa: E402  (import after cold_start so engine/secrets are ready)
from mangum import Mangum          # noqa: E402
handler = Mangum(app, lifespan="off")
