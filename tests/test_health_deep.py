import pytest

from app import observability


@pytest.fixture(autouse=True)
def reset_health_cache():
    observability._HEALTH_CACHE["expires_at"] = 0.0
    observability._HEALTH_CACHE["payload"] = None


@pytest.mark.asyncio
async def test_health_deep_reports_healthy(client, monkeypatch):
    async def _database():
        return {"status": "up", "latency_ms": 1.2}

    async def _redis():
        return {"status": "up", "latency_ms": 0.9}

    async def _storage():
        return {"status": "up", "writable": True, "free_gb": 12.5}

    async def _celery():
        return {"status": "up", "workers": 1}

    monkeypatch.setattr(observability, "_check_database", _database)
    monkeypatch.setattr(observability, "_check_redis", _redis)
    monkeypatch.setattr(observability, "_check_storage", _storage)
    monkeypatch.setattr(observability, "_check_celery", _celery)

    response = await client.get("/health/deep")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["checks"]["database"]["status"] == "up"
    assert body["checks"]["redis"]["status"] == "up"
    assert body["checks"]["storage"]["writable"] is True
    assert body["checks"]["celery"]["workers"] == 1
    assert body["version"] == "0.1.0"


@pytest.mark.asyncio
async def test_health_deep_reports_degraded_when_only_celery_is_down(client, monkeypatch):
    monkeypatch.setattr(observability, "_check_database", lambda: _async_result({"status": "up", "latency_ms": 1.1}))
    monkeypatch.setattr(observability, "_check_redis", lambda: _async_result({"status": "up", "latency_ms": 0.8}))
    monkeypatch.setattr(observability, "_check_storage", lambda: _async_result({"status": "up", "writable": True, "free_gb": 8.0}))
    monkeypatch.setattr(observability, "_check_celery", lambda: _async_result({"status": "down", "workers": 0}))

    response = await client.get("/health/deep")

    assert response.status_code == 200
    assert response.json()["status"] == "degraded"


@pytest.mark.asyncio
async def test_health_deep_reports_unhealthy_when_database_is_down(client, monkeypatch):
    monkeypatch.setattr(observability, "_check_database", lambda: _async_result({"status": "down", "latency_ms": 3000.0}))
    monkeypatch.setattr(observability, "_check_redis", lambda: _async_result({"status": "up", "latency_ms": 0.7}))
    monkeypatch.setattr(observability, "_check_storage", lambda: _async_result({"status": "up", "writable": True, "free_gb": 8.0}))
    monkeypatch.setattr(observability, "_check_celery", lambda: _async_result({"status": "up", "workers": 1}))

    response = await client.get("/health/deep")

    assert response.status_code == 200
    assert response.json()["status"] == "unhealthy"


@pytest.mark.asyncio
async def test_health_deep_caches_results_for_ten_seconds(client, monkeypatch):
    calls = {"count": 0}

    async def _database():
        calls["count"] += 1
        return {"status": "up", "latency_ms": 1.0}

    monkeypatch.setattr(observability, "_check_database", _database)
    monkeypatch.setattr(observability, "_check_redis", lambda: _async_result({"status": "up", "latency_ms": 0.7}))
    monkeypatch.setattr(observability, "_check_storage", lambda: _async_result({"status": "up", "writable": True, "free_gb": 8.0}))
    monkeypatch.setattr(observability, "_check_celery", lambda: _async_result({"status": "up", "workers": 1}))

    first = await client.get("/health/deep")
    second = await client.get("/health/deep")

    assert first.status_code == 200
    assert second.status_code == 200
    assert calls["count"] == 1


async def _async_result(value):
    return value
