import uuid

import pytest

from app import observability


@pytest.fixture(autouse=True)
def reset_metrics_state():
    observability._REQUEST_COUNTS.clear()
    observability._CREDIT_TOTALS.clear()


@pytest.mark.asyncio
async def test_metrics_exposes_prometheus_format(client):
    observability.record_credit_metric("debit", 3)
    observability.record_credit_metric("credit", 7)

    response = await client.get("/metrics")

    assert response.status_code == 200
    body = response.text
    assert "# HELP clipia_requests_total Total requests" in body
    assert "# TYPE clipia_active_jobs gauge" in body
    assert '# HELP clipia_credits_total Total credits transacted' in body
    assert 'clipia_credits_total{type="credit"} 7.0' in body
    assert 'clipia_credits_total{type="debit"} 3.0' in body


@pytest.mark.asyncio
async def test_metrics_counts_requests_by_method_path_and_status(client, verified_user, auth_headers):
    ok = await client.get("/api/v1/auth/me", headers=auth_headers(verified_user))
    missing_job_id = uuid.uuid4()
    missing = await client.get(f"/api/v1/jobs/{missing_job_id}", headers=auth_headers(verified_user))
    metrics = await client.get("/metrics")

    assert ok.status_code == 200
    assert missing.status_code == 404

    body = metrics.text
    assert 'clipia_requests_total{method="GET",path="/api/v1/auth/me",status="200"} 1' in body
    assert f'clipia_requests_total{{method="GET",path="/api/v1/jobs/{missing_job_id}",status="404"}} 1' in body
    assert 'clipia_active_jobs{status="queued"}' in body
    assert 'clipia_active_jobs{status="processing"}' in body
