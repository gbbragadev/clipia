from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_generate_returns_job_id():
    with patch("app.api.routes.dispatch_pipeline") as mock_dispatch:
        resp = client.post("/api/v1/generate", json={
            "topic": "5 curiosidades sobre o oceano",
            "style": "educational",
            "duration_target": 45,
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "job_id" in data
    assert data["status"] == "queued"
    mock_dispatch.assert_called_once()


def test_generate_validates_topic_min_length():
    resp = client.post("/api/v1/generate", json={"topic": "abc"})
    assert resp.status_code == 422


def test_job_status_not_found():
    with patch("app.api.routes._redis") as mock_redis:
        mock_redis.hgetall.return_value = {}
        resp = client.get("/api/v1/jobs/nonexistent")
    assert resp.status_code == 404
