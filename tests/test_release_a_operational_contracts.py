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
        del body, token, extra_headers
        if method == "GET" and url.endswith("/health"):
            return 200, {"status": "ok"}
        if url.endswith("/auth/register"):
            return 201, {"access_token": "readiness-token"}
        if url.endswith("/auth/verify-email"):
            return 200, {"credits": 2}
        if url.endswith("/generate"):
            return generate_status, {"job_id": "job-readiness-123", "credit_cost": 1}
        raise AssertionError(f"request inesperada: {method} {url}")

    monkeypatch.setattr(validate_readiness, "_http", fake_http)
    monkeypatch.setattr(validate_readiness, "_db", lambda: _async_result(FakeConnection()))
    monkeypatch.setattr(validate_readiness, "check_resend_domain", lambda: None)
    monkeypatch.setattr(validate_readiness, "_mark", lambda level, message: marks.append((level, message)))

    await validate_readiness.run("http://clipia.test", make_video=False)

    assert not [message for level, message in marks if level == "FAIL"]
    assert any(level == "PASS" and "Geracao enfileirada" in message for level, message in marks)


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
