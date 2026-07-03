import pytest

from app.auth import routes as auth_routes
from app.db.models import User


@pytest.mark.asyncio
async def test_update_name_works(client, db_session, verified_user, auth_headers):
    response = await client.patch(
        "/api/v1/auth/me",
        headers=auth_headers(verified_user),
        json={"name": "Novo Nome"},
    )

    assert response.status_code == 200
    refreshed = await db_session.get(User, verified_user.id)
    assert refreshed is not None
    assert refreshed.name == "Novo Nome"


@pytest.mark.asyncio
async def test_update_with_empty_name_fails(client, verified_user, auth_headers):
    response = await client.patch(
        "/api/v1/auth/me",
        headers=auth_headers(verified_user),
        json={"name": "   "},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_change_password_with_wrong_current_password_fails(client, verified_user, auth_headers):
    response = await client.post(
        "/api/v1/auth/change-password",
        headers=auth_headers(verified_user),
        json={"current_password": "wrong", "new_password": "NewSecret123"},
    )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_change_password_works_and_login_uses_new_password(client, verified_user, auth_headers):
    response = await client.post(
        "/api/v1/auth/change-password",
        headers=auth_headers(verified_user),
        json={"current_password": "supersecret", "new_password": "NewSecret123"},
    )
    login_new = await client.post(
        "/api/v1/auth/login",
        json={"email": verified_user.email, "password": "NewSecret123"},
    )
    login_old = await client.post(
        "/api/v1/auth/login",
        json={"email": verified_user.email, "password": "supersecret"},
    )

    assert response.status_code == 200
    assert login_new.status_code == 200
    assert login_old.status_code == 401


@pytest.mark.asyncio
async def test_change_password_enforces_strength_policy(client, verified_user, auth_headers):
    """A troca de senha deve aplicar a mesma politica de forca do cadastro
    (8+ chars, 1 maiuscula, 1 digito) para que a politica seja uniforme."""
    # Sem maiuscula/digito -> rejeitado (422 de validacao do Pydantic)
    weak = await client.post(
        "/api/v1/auth/change-password",
        headers=auth_headers(verified_user),
        json={"current_password": "supersecret", "new_password": "newsecret"},
    )
    # Menos de 8 chars -> rejeitado
    too_short = await client.post(
        "/api/v1/auth/change-password",
        headers=auth_headers(verified_user),
        json={"current_password": "supersecret", "new_password": "Ab1"},
    )
    # Conforme a politica -> aceito
    strong = await client.post(
        "/api/v1/auth/change-password",
        headers=auth_headers(verified_user),
        json={"current_password": "supersecret", "new_password": "NewSecret123"},
    )

    assert weak.status_code == 422
    assert too_short.status_code == 422
    assert strong.status_code == 200


@pytest.mark.asyncio
async def test_delete_account_anonymizes_and_invalidates_token(client, db_session, verified_user, auth_headers):
    auth_routes.send_account_deleted_email.reset_mock()

    response = await client.post(
        "/api/v1/auth/delete-account",
        headers=auth_headers(verified_user),
        json={"password": "supersecret"},
    )

    assert response.status_code == 200
    refreshed = await db_session.get(User, verified_user.id)
    assert refreshed is not None
    assert refreshed.plan == "deleted"
    assert refreshed.name == "Deleted User"
    assert refreshed.email.endswith("@removed.clipia.com.br")
    assert refreshed.credits == 0
    assert auth_routes.send_account_deleted_email.call_count == 1

    me = await client.get("/api/v1/auth/me", headers=auth_headers(verified_user))
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "verified@example.com", "password": "supersecret"},
    )

    assert me.status_code == 401
    assert login.status_code == 401


@pytest.mark.asyncio
async def test_export_data_returns_user_jobs_and_purchases(
    client, verified_user, auth_headers, job_factory, purchase_factory
):
    await job_factory(user_id=verified_user.id, status="completed")
    await purchase_factory(user_id=verified_user.id, package_name="starter", status="approved")

    response = await client.get("/api/v1/auth/export-data", headers=auth_headers(verified_user))

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["email"] == verified_user.email
    assert len(body["jobs"]) == 1
    assert len(body["purchases"]) == 1
