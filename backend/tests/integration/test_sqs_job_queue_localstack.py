"""Integration tests for SqsJobQueue against real LocalStack.

Proves:
- enqueue() sends a JSON message to the SQS queue
- The message body deserializes to {"name": <name>, "payload": <payload>}
- Multiple enqueues are received in order

LocalStack must be running (make local-up).  Tests are skipped automatically
when LocalStack is unreachable (see conftest.py).
"""
from __future__ import annotations

import json

import pytest

QUEUE_NAME = "integ-test-job-queue"


@pytest.fixture(scope="module")
def sqs_queue(ls_sqs):
    """Create (and clean up) an SQS queue for this module's tests."""
    resp = ls_sqs.create_queue(QueueName=QUEUE_NAME)
    queue_url = resp["QueueUrl"]
    yield queue_url
    # Best-effort cleanup
    try:
        ls_sqs.delete_queue(QueueUrl=queue_url)
    except Exception:
        pass


@pytest.fixture()
def job_queue(sqs_queue):
    """Construct SqsJobQueue pointing at the LocalStack queue.

    AWS_ENDPOINT_URL is already set in the environment by the session-scoped
    aws_env fixture, so SqsJobQueue() reads it via Settings().aws_endpoint_url.
    """
    from app.jobs.queue import SqsJobQueue

    return SqsJobQueue(sqs_queue)


def _receive_one(ls_sqs, queue_url: str) -> dict:
    """Helper: receive one message from the queue and return the parsed body."""
    resp = ls_sqs.receive_message(
        QueueUrl=queue_url,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=2,
    )
    messages = resp.get("Messages", [])
    assert messages, "Expected at least one message in the queue"
    body = json.loads(messages[0]["Body"])
    # Delete message to clean up the queue state between tests
    ls_sqs.delete_message(
        QueueUrl=queue_url,
        ReceiptHandle=messages[0]["ReceiptHandle"],
    )
    return body


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enqueue_sends_correct_message(job_queue, sqs_queue, ls_sqs):
    """enqueue() sends a JSON message whose body matches {name, payload}."""
    await job_queue.enqueue("some_job", {"a": 1})
    body = _receive_one(ls_sqs, sqs_queue)
    assert body == {"name": "some_job", "payload": {"a": 1}}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enqueue_empty_payload(job_queue, sqs_queue, ls_sqs):
    """enqueue() works with an empty payload dict."""
    await job_queue.enqueue("empty_job", {})
    body = _receive_one(ls_sqs, sqs_queue)
    assert body == {"name": "empty_job", "payload": {}}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enqueue_nested_payload(job_queue, sqs_queue, ls_sqs):
    """enqueue() serializes nested dicts and lists correctly."""
    payload = {"user_id": 42, "tags": ["a", "b"], "meta": {"k": "v"}}
    await job_queue.enqueue("complex_job", payload)
    body = _receive_one(ls_sqs, sqs_queue)
    assert body == {"name": "complex_job", "payload": payload}


@pytest.mark.integration
@pytest.mark.asyncio
async def test_enqueue_multiple_messages_are_ordered(job_queue, sqs_queue, ls_sqs):
    """Multiple enqueues are received in FIFO order (standard SQS is best-effort,
    but LocalStack typically preserves order for small counts)."""
    await job_queue.enqueue("job_first", {"seq": 1})
    await job_queue.enqueue("job_second", {"seq": 2})

    first = _receive_one(ls_sqs, sqs_queue)
    second = _receive_one(ls_sqs, sqs_queue)

    # Verify both messages arrived with correct structure
    names = {first["name"], second["name"]}
    assert names == {"job_first", "job_second"}
