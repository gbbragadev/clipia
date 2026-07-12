import pytest

from app.db.models import Job, User


@pytest.mark.asyncio
async def test_generate_debits_exactly_one_credit(client, db_session, verified_user, auth_headers, app):
    before = (await db_session.get(User, verified_user.id)).credits

    response = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json={"topic": "Tema valido para gerar video", "style": "educational", "duration_target": 45},
    )

    assert response.status_code == 200, "Generate should succeed for verified users with credits."
    after = (await db_session.get(User, verified_user.id)).credits
    assert before - after == 1, "Generate should debit exactly one credit."
    app.state.dispatch_pipeline.assert_called_once()


@pytest.mark.asyncio
async def test_generate_ai_image_template_debits_ai_image_floor(client, db_session, verified_user, auth_headers, app):
    before = (await db_session.get(User, verified_user.id)).credits

    response = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json={
            "topic": "Tema valido para novelinha historica",
            "style": "storytelling",
            "duration_target": 45,
            "template_id": "novelinha_historica",
            "voice_provider": "edge",
        },
    )

    assert response.status_code == 200
    assert response.json()["credit_cost"] == 5
    after = (await db_session.get(User, verified_user.id)).credits
    assert before - after == 5
    job = await db_session.get(Job, response.json()["job_id"])
    assert job.credit_cost == 5
    app.state.dispatch_pipeline.assert_called_once()


@pytest.mark.asyncio
async def test_generate_with_zero_credits_returns_402(client, db_session, verified_user, auth_headers):
    db_user = await db_session.get(User, verified_user.id)
    db_user.credits = 0
    await db_session.commit()

    response = await client.post(
        "/api/v1/generate",
        headers=auth_headers(verified_user),
        json={"topic": "Tema valido para gerar video", "style": "educational", "duration_target": 45},
    )

    assert response.status_code == 402, "Generate should return 402 when credits are insufficient."
    fresh_user = await db_session.get(User, verified_user.id)
    assert fresh_user.credits == 0, "Rejected generate calls must not partially debit credits."


@pytest.mark.asyncio
async def test_ai_suggest_only_charges_after_success(
    client, db_session, job_factory, verified_user, auth_headers, monkeypatch
):
    job = await job_factory()

    monkeypatch.setattr(
        "app.api.routes.complete_text",
        lambda *a, **k: '{"suggestions":[],"general_feedback":"ok"}',
    )

    response = await client.post(
        f"/api/v1/jobs/{job.id}/ai-suggest",
        headers=auth_headers(verified_user),
        json={"message": "melhore o roteiro", "context": {"scenes": []}},
    )
    assert response.status_code == 200, "Successful AI suggestions should return 200."

    refreshed_job = await db_session.get(Job, job.id)
    assert refreshed_job.pending_credits == 0.5, "Successful AI suggestions should add exactly 0.5 pending credits."


@pytest.mark.asyncio
async def test_ai_suggest_external_failure_does_not_charge(
    client, db_session, job_factory, verified_user, auth_headers, monkeypatch
):
    job = await job_factory()

    def _boom(*a, **k):
        raise RuntimeError("OpenRouter unavailable")

    monkeypatch.setattr("app.api.routes.complete_text", _boom)

    response = await client.post(
        f"/api/v1/jobs/{job.id}/ai-suggest",
        headers=auth_headers(verified_user),
        json={"message": "melhore o roteiro", "context": {"scenes": []}},
    )
    assert (
        response.status_code == 502
    ), "Falha do LLM upstream no ai-suggest deve virar 502 (Bad Gateway), com mensagem amigavel."

    refreshed_job = await db_session.get(Job, job.id)
    assert refreshed_job.pending_credits == 0.0, "Failed AI suggestions must not add pending credits."


@pytest.mark.asyncio
async def test_render_debits_pending_credits_once_and_resets_job(
    client, db_session, job_factory, verified_user, auth_headers, storage_dir, app
):
    job = await job_factory(pending_credits=2.0)
    job_dir = storage_dir / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)

    before = (await db_session.get(User, verified_user.id)).credits
    response = await client.post(f"/api/v1/jobs/{job.id}/render", headers=auth_headers(verified_user))

    assert response.status_code == 200, "Render should succeed when the user can pay pending credits."
    refreshed_job = await db_session.get(Job, job.id)
    refreshed_user = await db_session.get(User, verified_user.id)
    assert before - refreshed_user.credits == 2, "Render should debit the full pending-credit amount."
    assert refreshed_job.pending_credits == 0.0, "Render should clear pending credits after charging."
    app.state.rerender_task.delay.assert_called_once_with(str(job.id))


@pytest.mark.asyncio
async def test_reset_debits_one_credit_and_clears_editor_state(
    client, db_session, job_factory, verified_user, auth_headers
):
    job = await job_factory(pending_credits=1.5, editor_state={"composition": {"scenes": []}})
    before = (await db_session.get(User, verified_user.id)).credits

    response = await client.post(f"/api/v1/jobs/{job.id}/reset", headers=auth_headers(verified_user))

    assert response.status_code == 200, "Reset should succeed for users with one credit remaining."
    refreshed_job = await db_session.get(Job, job.id)
    refreshed_user = await db_session.get(User, verified_user.id)
    assert before - refreshed_user.credits == 1, "Reset should debit exactly one credit."
    assert refreshed_job.pending_credits == 0.0, "Reset should clear pending credits."
    assert refreshed_job.editor_state is None, "Reset should clear editor state."


@pytest.mark.asyncio
async def test_refund_failure_does_not_mask_original_error(
    client, db_session, verified_user, auth_headers, monkeypatch
):
    """Achado R1 12/07: excecao no refund substituia o erro ORIGINAL da acao paga e o
    cliente via 500 generico. O _refund_credits_safe engole a falha do estorno, alerta
    o admin (estorno manual) e preserva o 502 da causa real."""
    alerts = []
    monkeypatch.setattr("app.api.routes._send_admin_alert", lambda subject, body: alerts.append(subject))

    async def boom_design(self, *a, **k):
        raise RuntimeError("elevenlabs caiu")

    monkeypatch.setattr("app.services.elevenlabs_provider.ElevenLabsProvider.design_voice", boom_design)

    async def refund_boom(db, user_id, cost):
        raise RuntimeError("banco caiu no estorno")

    monkeypatch.setattr("app.api.routes._refund_credits", refund_boom)

    response = await client.post(
        "/api/v1/voices/design",
        headers=auth_headers(verified_user),
        json={
            "name": "Voz Teste",
            "description": "voz grave e calma para narracao",
            "text": "Ola, este e um teste de voz.",
        },
    )

    assert response.status_code == 502, "Falha da acao paga deve continuar 502 mesmo com refund quebrado."
    assert "voz" in response.json()["detail"].lower(), "Detail deve apontar a causa original (TTS), nao o refund."
    assert alerts, "Refund que falhou de vez precisa disparar alerta admin para estorno manual."
