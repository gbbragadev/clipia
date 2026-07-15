import tomllib
from pathlib import Path

import pytest

from app import observability
from app.config import Settings, settings
from scripts import predeploy_check, validate_readiness

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_ci_installs_project_dev_extra_and_generates_next_types_before_tsc():
    workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert 'python -m pip install -e ".[dev]"' in workflow
    assert "requirements.txt" not in workflow
    assert "--timeout=60" in workflow
    assert workflow.index("npx next typegen") < workflow.index("npx tsc --noEmit")


def test_dev_extra_declares_pytest_timeout_used_by_ci():
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    dev_dependencies = project["project"]["optional-dependencies"]["dev"]
    assert any(dependency.startswith("pytest-timeout") for dependency in dev_dependencies)


@pytest.mark.asyncio
@pytest.mark.parametrize("generate_status", [200, 202])
async def test_readiness_accepts_queued_generation_with_job_id(monkeypatch, generate_status):
    marks: list[tuple[str, str]] = []

    class FakeConnection:
        async def fetchval(self, query, _email):
            if "verification_code" in query:
                return "123456"
            return None

        async def close(self):
            return None

    def fake_http(method, url, body=None, token=None, extra_headers=None):
        del token, extra_headers
        if method == "GET" and url.endswith("/health"):
            return 200, {"status": "ok"}
        if url.endswith("/auth/register"):
            assert body["consent"] is True
            return 201, {"access_token": "readiness-token"}
        if url.endswith("/auth/verify-email"):
            return 200, {"credits": 2}
        if url.endswith("/generate"):
            return generate_status, {"job_id": "job-readiness-123", "credit_cost": 1}
        if url.endswith("/auth/delete-account"):
            return 200, {"status": "account_deleted"}
        raise AssertionError(f"request inesperada: {method} {url}")

    monkeypatch.setattr(validate_readiness, "_http", fake_http)
    monkeypatch.setattr(validate_readiness, "_db", lambda: _async_result(FakeConnection()))
    monkeypatch.setattr(validate_readiness, "check_resend_domain", lambda: None)
    monkeypatch.setattr(validate_readiness, "_mark", lambda level, message: marks.append((level, message)))

    await validate_readiness.run("http://clipia.test", make_video=False)

    assert not [message for level, message in marks if level == "FAIL"]
    assert any(level == "PASS" and "Geracao enfileirada" in message for level, message in marks)


@pytest.mark.asyncio
async def test_readiness_full_activation_checks_preview_edit_render_download_and_credits(monkeypatch):
    assert hasattr(validate_readiness, "_http_bytes")
    marks: list[tuple[str, str]] = []
    calls: list[tuple[str, str]] = []
    saved_editor_state: dict | None = None

    class FakeConnection:
        async def fetchval(self, query, _value):
            if "verification_code" in query:
                return "123456"
            if "SELECT id" in query:
                return "qa-user-id"
            return None

        async def execute(self, *_args):
            return None

        async def close(self):
            return None

    async def no_sleep(_seconds):
        return None

    def fake_http(method, url, body=None, token=None, extra_headers=None):
        nonlocal saved_editor_state
        del token, extra_headers
        calls.append((method, url))
        if method == "GET" and url.endswith("/health"):
            return 200, {"status": "ok"}
        if method == "GET" and url.endswith("/health/deep"):
            return 200, {"status": "healthy", "checks": {"storage": {"worker_match": True}}}
        if url.endswith("/auth/register"):
            assert body["consent"] is True
            return 201, {"access_token": "readiness-token"}
        if url.endswith("/auth/verify-email"):
            return 200, {"credits": 2}
        if url.endswith("/generate"):
            return 202, {"job_id": "job-readiness-123", "credit_cost": 1}
        if method == "GET" and url.endswith("/jobs/job-readiness-123"):
            return 200, {"status": "editable", "progress": 1, "current_step": "finalizing"}
        if method == "GET" and url.endswith("/jobs/job-readiness-123/composition"):
            return 200, {
                "script": {"title": "QA", "scenes": [{"text": "Cena QA", "duration_hint": 3}]},
                "words": [{"word": "Cena", "start": 0.0, "end": 0.5}],
                "audio_url": "/storage/jobs/job-readiness-123/narration.wav",
                "media_urls": ["/storage/jobs/job-readiness-123/media/scene_0.mp4?exp=1&sig=qa"],
                "subtitle_style": {},
                "editor_state": None,
                "fps": 30,
                "width": 1080,
                "height": 1920,
                "template_id": "stock_narration",
                "layout_type": "fullscreen",
                "pending_credits": 0,
                "music_asset_id": "inspirational",
                "music_volume": 0.3,
            }
        if method == "POST" and url.endswith("/jobs/job-readiness-123/edit"):
            saved_editor_state = body
            return 200, {"status": "saved"}
        if method == "POST" and url.endswith("/jobs/job-readiness-123/render"):
            return 200, {"status": "rendering"}
        if method == "GET" and url.endswith("/jobs/job-readiness-123/status"):
            return 200, {"status": "completed", "progress": 1, "pending_credits": 0}
        if method == "GET" and url.endswith("/auth/me"):
            return 200, {"credits": 1}
        if url.endswith("/auth/delete-account"):
            return 200, {"status": "account_deleted"}
        raise AssertionError(f"request inesperada: {method} {url} body={body}")

    def fake_http_bytes(method, url, token=None, extra_headers=None):
        del token
        calls.append((method, url))
        if "/storage/jobs/" in url:
            assert extra_headers == {"Range": "bytes=0-1023"}
            return 206, b"media-range", {"content-range": "bytes 0-10/100"}
        if url.endswith("/jobs/job-readiness-123/download"):
            return 200, b"0" * 20_000, {"content-type": "video/mp4", "accept-ranges": "bytes"}
        raise AssertionError(f"download inesperado: {method} {url}")

    monkeypatch.setattr(validate_readiness, "_http", fake_http)
    monkeypatch.setattr(validate_readiness, "_http_bytes", fake_http_bytes)
    monkeypatch.setattr(validate_readiness, "_db", lambda: _async_result(FakeConnection()))
    monkeypatch.setattr(validate_readiness, "check_resend_domain", lambda: None)
    monkeypatch.setattr(validate_readiness, "_mark", lambda level, message: marks.append((level, message)))
    monkeypatch.setattr(validate_readiness.asyncio, "sleep", no_sleep)

    await validate_readiness.run("http://clipia.test", make_video=True)

    assert not [message for level, message in marks if level == "FAIL"]
    assert saved_editor_state is not None
    composition = saved_editor_state["editor_state"]["composition"]
    assert composition["subtitleStyle"]["preset"] == "neon"
    assert composition["musicAssetId"] == "lofi-chill"
    assert any(url.endswith("/jobs/job-readiness-123/render") for _, url in calls)
    assert any(url.endswith("/jobs/job-readiness-123/download") for _, url in calls)
    assert any(url.endswith("/auth/delete-account") for _, url in calls)
    assert any(level == "PASS" and "saldo" in message.lower() for level, message in marks)


@pytest.mark.asyncio
async def test_deep_health_exposes_allowlisted_build_provenance(client, monkeypatch):
    async def healthy_database():
        return {"status": "up", "latency_ms": 1.0}

    async def healthy_redis():
        return {"status": "up", "latency_ms": 1.0}

    async def healthy_storage():
        return {"status": "up", "writable": True, "free_gb": 10.0}

    async def healthy_celery():
        return {"status": "up", "workers": 1}

    monkeypatch.setattr(observability, "_check_database", healthy_database)
    monkeypatch.setattr(observability, "_check_redis", healthy_redis)
    monkeypatch.setattr(observability, "_check_storage", healthy_storage)
    monkeypatch.setattr(observability, "_check_celery", healthy_celery)
    monkeypatch.setattr(settings, "GIT_SHA", "abc1234")
    monkeypatch.setattr(settings, "APP_VERSION", "2026.07.13")
    monkeypatch.setattr(settings, "DEPLOYED_AT", "2026-07-13T01:00:00Z")
    observability._HEALTH_CACHE["expires_at"] = 0.0
    observability._HEALTH_CACHE["payload"] = None

    response = await client.get("/health/deep")

    assert response.status_code == 200
    body = response.json()
    assert body["git_sha"] == "abc1234"
    assert body["app_version"] == "2026.07.13"
    assert body["deployed_at"] == "2026-07-13T01:00:00Z"
    assert body["version"] == body["app_version"]
    assert not ({"jwt_secret", "smtp_password", "stripe_secret_key"} & set(body))


@pytest.mark.asyncio
async def test_deep_health_is_unhealthy_when_api_and_worker_storage_do_not_match(monkeypatch):
    async def healthy_database():
        return {"status": "up", "latency_ms": 1.0}

    async def healthy_redis():
        return {"status": "up", "latency_ms": 1.0}

    async def mismatched_storage():
        return {"status": "down", "writable": True, "free_gb": 10.0, "worker_match": False}

    async def healthy_celery():
        return {"status": "up", "workers": 1}

    monkeypatch.setattr(observability, "_check_database", healthy_database)
    monkeypatch.setattr(observability, "_check_redis", healthy_redis)
    monkeypatch.setattr(observability, "_check_storage", mismatched_storage)
    monkeypatch.setattr(observability, "_check_celery", healthy_celery)

    body = await observability._compute_deep_health("test")

    assert body["status"] == "unhealthy"
    assert body["checks"]["storage"]["worker_match"] is False


def test_predeploy_gate_rejects_api_worker_storage_mismatch(monkeypatch, tmp_path):
    assert hasattr(predeploy_check, "check_worker_storage_alignment")

    class FakeRedis:
        def __init__(self, value):
            self.value = value
            self.closed = False

        def get(self, key):
            assert key == "clipia:runtime:worker_storage_dir"
            return self.value

        def close(self):
            self.closed = True

    api_storage = tmp_path / "api-storage"
    worker_storage = tmp_path / "worker-storage"
    api_storage.mkdir()
    worker_storage.mkdir()
    monkeypatch.setattr(settings, "STORAGE_DIR", api_storage)

    mismatch = FakeRedis(str(worker_storage.resolve()))
    monkeypatch.setattr(predeploy_check, "get_redis", lambda: mismatch)
    with pytest.raises(predeploy_check.CheckFailure, match="storage"):
        predeploy_check.check_worker_storage_alignment()
    assert mismatch.closed is True

    aligned = FakeRedis(str(api_storage.resolve()))
    monkeypatch.setattr(predeploy_check, "get_redis", lambda: aligned)
    predeploy_check.check_worker_storage_alignment()
    assert aligned.closed is True


def test_build_provenance_defaults_are_non_secret_and_explicit():
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))

    assert Settings.model_fields["GIT_SHA"].default == "unknown"
    assert Settings.model_fields["DEPLOYED_AT"].default == "unknown"
    assert Settings.model_fields["APP_VERSION"].default == project["project"]["version"]


def test_predeploy_gate_requires_legacy_rerenders_to_be_drained(monkeypatch):
    class FakeRedis:
        def __init__(self, rows):
            self.rows = rows
            self.closed = False

        def scan_iter(self, **_kwargs):
            return iter(self.rows)

        def hgetall(self, key):
            return self.rows[key]

        def close(self):
            self.closed = True

    async def no_database_rows():
        return set()

    monkeypatch.setattr(predeploy_check, "_active_legacy_rerender_ids", no_database_rows)
    clean_redis = FakeRedis({})
    monkeypatch.setattr(predeploy_check, "get_redis", lambda: clean_redis)
    predeploy_check.check_no_legacy_rerenders()
    assert clean_redis.closed is True

    marker_redis = FakeRedis(
        {
            "job:legacy-active": {
                "rerender_cost": "2",
                "status": "rendering",
                "rerender_operation_id": "",
            }
        }
    )
    monkeypatch.setattr(predeploy_check, "get_redis", lambda: marker_redis)
    with pytest.raises(predeploy_check.CheckFailure, match="legacy-active"):
        predeploy_check.check_no_legacy_rerenders()
    assert marker_redis.closed is True


async def _async_result(value):
    return value
