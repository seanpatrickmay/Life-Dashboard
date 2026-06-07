"""Lambda cold-start bootstrap: secrets -> runtime validation -> DB engine."""
from __future__ import annotations
import os
from loguru import logger
from app.core.secrets import load_secrets_into_env

_COLD_STARTED = False


def _validate_runtime() -> None:
    if os.environ.get("LD_RUNTIME") != "aws":
        return
    # BLOCKING: InlineJobQueue uses asyncio.create_task (fire-and-forget) which is silently
    # dropped under Lambda. Require SQS so async work is never lost.
    if os.environ.get("LD_JOB_QUEUE") != "sqs":
        raise RuntimeError(
            "LD_RUNTIME=aws requires LD_JOB_QUEUE=sqs (inline async work is lost under Lambda). "
            f"Got LD_JOB_QUEUE={os.environ.get('LD_JOB_QUEUE')!r}."
        )
    # Non-blocking sanity warnings for the other backends (they fail loudly at use, not silently):
    for var, expected in (
        ("LD_BLOB_STORE", "s3"),
        ("LD_KV_STORE", "dynamodb"),
        ("LD_SECRETS", "secretsmanager"),
    ):
        if os.environ.get(var) != expected:
            logger.warning(
                "LD_RUNTIME=aws but {}={!r} (expected {!r})",
                var,
                os.environ.get(var),
                expected,
            )


def cold_start() -> None:
    """Idempotent: load secrets into env, validate runtime config, (re)build the DB engine."""
    global _COLD_STARTED
    if _COLD_STARTED:
        return
    injected = load_secrets_into_env()
    if injected:
        logger.info("cold_start: injected {} secret(s) into env", injected)
    _validate_runtime()
    from app.db.session import init_engine
    init_engine()
    _COLD_STARTED = True
