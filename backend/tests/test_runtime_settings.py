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
