"""Job queue abstraction for background work.

Backends
--------
InlineJobQueue  – default; runs the handler in-process via asyncio.create_task,
                  mirroring the current BackgroundTasks / asyncio.create_task behaviour.
                  Keeps the full test suite green with no external dependencies.

SqsJobQueue     – selected via ``LD_JOB_QUEUE=sqs``; publishes a JSON message to an
                  SQS queue for a worker Lambda to consume.  boto3 is imported lazily.

Factory
-------
``get_job_queue()`` reads a fresh ``Settings()`` at call time so that
``monkeypatch.setenv`` in tests is honoured — the module-level ``settings``
singleton is lru_cache'd and would not see env changes applied after import.

Worker entry-point
------------------
``dispatch(body)`` is the entry-point for the worker Lambda.  It reads the
``name`` and ``payload`` keys from the deserialized SQS message body and runs
the registered handler.
"""
from __future__ import annotations

import abc
import asyncio
import functools
import json

from loguru import logger

from app.core.config import Settings
from app.jobs.registry import get_handler


class JobQueue(abc.ABC):
    @abc.abstractmethod
    async def enqueue(self, name: str, payload: dict) -> None: ...


class InlineJobQueue(JobQueue):
    """Runs the handler in-process (mirrors current BackgroundTasks behaviour)."""

    async def enqueue(self, name: str, payload: dict) -> None:
        handler = get_handler(name)  # validate eagerly — fails fast on unknown names
        asyncio.create_task(handler(payload))


class SqsJobQueue(JobQueue):
    """Publishes a JSON message to SQS for a worker Lambda to consume."""

    def __init__(self, queue_url: str, *, client: object | None = None) -> None:
        import boto3  # lazy import — only required when SQS backend is selected

        self._url = queue_url
        # Read endpoint_url from a fresh Settings() so tests can override via env
        endpoint_url = Settings().aws_endpoint_url
        self._client = client or boto3.client("sqs", endpoint_url=endpoint_url or None)

    async def enqueue(self, name: str, payload: dict) -> None:
        body = json.dumps({"name": name, "payload": payload})
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            functools.partial(
                self._client.send_message,
                QueueUrl=self._url,
                MessageBody=body,
            ),
        )


async def dispatch(body: dict) -> None:
    """Run the registered handler for a ``{name, payload}`` message.

    Used as the entry-point for the worker Lambda when it receives an SQS event.

    Malformed or unknown messages are discarded (logged, not re-raised) to avoid
    infinite SQS retry loops.  Genuine handler exceptions DO propagate so SQS can
    retry / route to the DLQ.
    """
    name = body.get("name")
    if not name:
        logger.error("Job message missing 'name'; discarding: {}", body)
        return
    try:
        handler = get_handler(name)
    except KeyError:
        logger.error("No handler registered for job {!r}; discarding", name)
        return
    await handler(body.get("payload", {}))   # real handler errors propagate (SQS retry/DLQ)


def get_job_queue() -> JobQueue:
    """Return the configured job queue backend.

    Constructs a fresh ``Settings()`` at call time so that ``monkeypatch.setenv``
    in tests is respected — the module-level ``settings`` singleton is
    ``lru_cache``'d and would not see env changes applied after import.
    """
    s = Settings()
    if s.ld_job_queue == "sqs":
        return SqsJobQueue(s.sqs_queue_url or "")
    return InlineJobQueue()
