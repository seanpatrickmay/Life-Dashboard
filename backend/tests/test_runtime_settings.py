from app.core.config import Settings


def test_defaults_preserve_local_behavior():
    s = Settings()
    assert s.ld_blob_store == "local"
    assert s.ld_job_queue == "inline"
    assert s.ld_kv_store == "memory"
    assert s.ld_secrets == "env"
    assert s.ld_garmin_tokens == "db"


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("LD_BLOB_STORE", "s3")
    monkeypatch.setenv("LD_JOB_QUEUE", "sqs")
    s = Settings()
    assert s.ld_blob_store == "s3"
    assert s.ld_job_queue == "sqs"


# ---------------------------------------------------------------------------
# Regression tests for AWS-handle fields: verify LD_*-prefixed env vars map
# correctly. These tests caught the pydantic-settings v2 `env=` silent-ignore
# bug where Field(..., env="X") was ignored and the field name was used instead.
# ---------------------------------------------------------------------------

def test_ld_s3_asset_bucket_reads_ld_prefixed_env(monkeypatch):
    """LD_S3_ASSET_BUCKET must map to s3_asset_bucket (not S3_ASSET_BUCKET)."""
    monkeypatch.setenv("LD_S3_ASSET_BUCKET", "my-bucket")
    s = Settings()
    assert s.s3_asset_bucket == "my-bucket"


def test_ld_sqs_queue_url_reads_ld_prefixed_env(monkeypatch):
    """LD_SQS_QUEUE_URL must map to sqs_queue_url (not SQS_QUEUE_URL)."""
    monkeypatch.setenv("LD_SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123/my-queue")
    s = Settings()
    assert s.sqs_queue_url == "https://sqs.us-east-1.amazonaws.com/123/my-queue"


def test_ld_ddb_kv_table_reads_ld_ddb_prefixed_env(monkeypatch):
    """LD_DDB_KV_TABLE must map to dynamodb_kv_table (not DYNAMODB_KV_TABLE)."""
    monkeypatch.setenv("LD_DDB_KV_TABLE", "my-kv-table")
    s = Settings()
    assert s.dynamodb_kv_table == "my-kv-table"


def test_ld_secrets_name_reads_ld_prefixed_env(monkeypatch):
    """LD_SECRETS_NAME must map to secrets_name (not SECRETS_NAME)."""
    monkeypatch.setenv("LD_SECRETS_NAME", "prod/life-dashboard/secrets")
    s = Settings()
    assert s.secrets_name == "prod/life-dashboard/secrets"


def test_aws_region_reads_aws_region_env(monkeypatch):
    """AWS_REGION must map to aws_region."""
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    s = Settings()
    assert s.aws_region == "eu-west-1"


def test_aws_endpoint_url_reads_aws_endpoint_url_env(monkeypatch):
    """AWS_ENDPOINT_URL must map to aws_endpoint_url."""
    monkeypatch.setenv("AWS_ENDPOINT_URL", "http://localhost:4566")
    s = Settings()
    assert s.aws_endpoint_url == "http://localhost:4566"


def test_wrong_env_name_does_not_set_s3_asset_bucket(monkeypatch):
    """S3_ASSET_BUCKET (missing LD_ prefix) must NOT populate s3_asset_bucket."""
    monkeypatch.delenv("LD_S3_ASSET_BUCKET", raising=False)
    monkeypatch.setenv("S3_ASSET_BUCKET", "wrong-bucket")
    s = Settings()
    assert s.s3_asset_bucket is None


def test_wrong_env_name_does_not_set_dynamodb_kv_table(monkeypatch):
    """DYNAMODB_KV_TABLE (missing LD_DDB_ prefix) must NOT populate dynamodb_kv_table."""
    monkeypatch.delenv("LD_DDB_KV_TABLE", raising=False)
    monkeypatch.setenv("DYNAMODB_KV_TABLE", "wrong-table")
    s = Settings()
    assert s.dynamodb_kv_table is None
