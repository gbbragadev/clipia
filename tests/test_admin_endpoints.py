"""Endpoints admin: listas paginadas (users/purchases/jobs) e ajuste manual de creditos auditado."""

import pytest
from sqlalchemy import select

from app.db.models import CreditAdjustment, User


@pytest.mark.asyncio
async def test_admin_users_list_with_search(client, admin_user, verified_user, auth_headers):
    response = await client.get("/api/v1/admin/users", params={"search": "verified@"}, headers=auth_headers(admin_user))

    assert response.status_code == 200
    data = response.json()
    emails = [u["email"] for u in data["users"]]
    assert "verified@example.com" in emails
    assert "admin@example.com" not in emails, "Busca deve filtrar por email/nome."
    assert data["total"] == len(data["users"])


@pytest.mark.asyncio
async def test_admin_purchases_filter_by_status(client, admin_user, purchase_factory, auth_headers):
    await purchase_factory(package_name="starter", status="pending")
    await purchase_factory(package_name="popular", status="approved")

    response = await client.get(
        "/api/v1/admin/purchases", params={"status": "approved"}, headers=auth_headers(admin_user)
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["purchases"][0]["package_name"] == "popular"
    assert data["purchases"][0]["user_email"] == "verified@example.com", "Lista traz o email via join."
    assert "bonus_credits" in data["purchases"][0]
    assert data["purchases"][0]["status"] == "paid"


@pytest.mark.asyncio
async def test_admin_purchases_filter_uses_canonical_state_precedence(
    client, admin_user, purchase_factory, auth_headers
):
    await purchase_factory(package_name="starter", status="approved", payment_state="refunded")
    await purchase_factory(package_name="popular", status="pending", payment_state="paid")

    paid = await client.get("/api/v1/admin/purchases", params={"status": "paid"}, headers=auth_headers(admin_user))
    refunded = await client.get(
        "/api/v1/admin/purchases", params={"status": "refunded"}, headers=auth_headers(admin_user)
    )

    assert paid.status_code == refunded.status_code == 200
    assert [item["package_name"] for item in paid.json()["purchases"]] == ["popular"]
    assert [item["status"] for item in paid.json()["purchases"]] == ["paid"]
    assert [item["package_name"] for item in refunded.json()["purchases"]] == ["starter"]
    assert [item["status"] for item in refunded.json()["purchases"]] == ["refunded"]


@pytest.mark.asyncio
async def test_admin_jobs_list(client, admin_user, job_factory, auth_headers):
    await job_factory(status="completed")

    response = await client.get("/api/v1/admin/jobs", params={"status": "completed"}, headers=auth_headers(admin_user))

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["jobs"][0]["user_email"] == "verified@example.com"
    assert data["jobs"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_admin_adjust_credits_creates_audit(client, db_session, admin_user, verified_user, auth_headers):
    response = await client.post(
        f"/api/v1/admin/users/{verified_user.id}/adjust-credits",
        json={"delta": 10, "reason": "bonus beta tester"},
        headers=auth_headers(admin_user),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["previous_balance"] == 5
    assert body["new_balance"] == 15

    db_session.expire_all()
    assert (await db_session.get(User, verified_user.id)).credits == 15
    audit = (
        (await db_session.execute(select(CreditAdjustment).where(CreditAdjustment.target_user_id == verified_user.id)))
        .scalars()
        .all()
    )
    assert len(audit) == 1, "Ajuste manual de creditos exige trilha de auditoria."
    assert audit[0].admin_user_id == admin_user.id
    assert audit[0].delta == 10
    assert audit[0].reason == "bonus beta tester"


@pytest.mark.asyncio
async def test_admin_adjust_credits_clamps_at_zero(client, db_session, admin_user, verified_user, auth_headers):
    response = await client.post(
        f"/api/v1/admin/users/{verified_user.id}/adjust-credits",
        json={"delta": -100, "reason": "estorno manual"},
        headers=auth_headers(admin_user),
    )

    assert response.status_code == 200
    assert response.json()["new_balance"] == 0, "Saldo nunca fica negativo."
    db_session.expire_all()
    assert (await db_session.get(User, verified_user.id)).credits == 0


@pytest.mark.asyncio
async def test_admin_adjust_credits_validation(client, admin_user, verified_user, auth_headers):
    zero = await client.post(
        f"/api/v1/admin/users/{verified_user.id}/adjust-credits",
        json={"delta": 0, "reason": "motivo valido"},
        headers=auth_headers(admin_user),
    )
    short_reason = await client.post(
        f"/api/v1/admin/users/{verified_user.id}/adjust-credits",
        json={"delta": 5, "reason": "ab"},
        headers=auth_headers(admin_user),
    )

    assert zero.status_code == 422, "Delta 0 nao e um ajuste."
    assert short_reason.status_code == 422, "Motivo e obrigatorio (auditoria)."


@pytest.mark.asyncio
async def test_admin_adjust_credits_unknown_user_404(client, admin_user, auth_headers):
    response = await client.post(
        "/api/v1/admin/users/00000000-0000-0000-0000-000000000000/adjust-credits",
        json={"delta": 5, "reason": "motivo valido"},
        headers=auth_headers(admin_user),
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_admin_endpoints_forbidden_for_non_admin(client, verified_user, auth_headers):
    headers = auth_headers(verified_user)

    for path in ("/api/v1/admin/users", "/api/v1/admin/purchases", "/api/v1/admin/jobs"):
        response = await client.get(path, headers=headers)
        assert response.status_code == 403, f"{path} deve ser restrito a admin."

    adjust = await client.post(
        f"/api/v1/admin/users/{verified_user.id}/adjust-credits",
        json={"delta": 5, "reason": "motivo valido"},
        headers=headers,
    )
    assert adjust.status_code == 403
