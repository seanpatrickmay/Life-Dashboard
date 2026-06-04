"""SQS -> job dispatch worker Lambda (partial-batch-failure reporting)."""
from __future__ import annotations

import asyncio
import json

from loguru import logger

from app.aws.bootstrap import cold_start

cold_start()  # MUST run before the imports below: loads secrets (DATABASE_URL) into env
              # before app.core.config's module-level Settings() is constructed.

# Import handler modules so their @job registrations populate the registry:
import app.jobs.handlers  # noqa: F401, E402
import app.workers.tasks  # noqa: F401, E402

from app.jobs.queue import dispatch  # noqa: E402


def handler(event: dict | None, context: object = None) -> dict:
    """SQS Lambda entry-point.

    Calls cold_start() (idempotent), then runs a single asyncio.run() for the
    entire batch — required for NullPool/asyncpg correctness.

    Returns the AWS partial-batch-failure shape::

        {"batchItemFailures": [{"itemIdentifier": "<messageId>"}, ...]}

    Records that fail (handler raises or body JSON is unparseable) are reported
    here; SQS retries them / routes to DLQ when ReportBatchItemFailures is set
    on the event source mapping (configured in Phase 4 CDK).  Records that
    dispatch() handles gracefully (unknown/malformed job names) are NOT failures
    from SQS's perspective and are therefore NOT included in batchItemFailures.
    """
    cold_start()  # idempotent no-op (already ran at import); kept for safety
    return asyncio.run(_process(event or {}))


async def _process(event: dict) -> dict:
    failures: list[dict] = []
    for record in event.get("Records", []):
        message_id = record.get("messageId")
        try:
            body = json.loads(record["body"])
            await dispatch(body)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Worker failed for SQS message {}: {}", message_id, exc)
            if message_id:
                failures.append({"itemIdentifier": message_id})
    return {"batchItemFailures": failures}
