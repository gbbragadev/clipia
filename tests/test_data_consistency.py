import json

import pytest
from sqlalchemy import delete

from app.db.models import CreditPurchase, Job, User


@pytest.mark.asyncio
async def test_edit_persists_editor_state_and_composition_reads_it(
    client, db_session, job_factory, verified_user, auth_headers, storage_dir
):
    job = await job_factory(script={"scenes": [{"text": "scene 1"}]}, editor_state=None)
    job_dir = storage_dir / "jobs" / str(job.id)
    (job_dir / "media").mkdir(parents=True)
    (job_dir / "script.json").write_text(json.dumps({"scenes": [{"text": "scene 1"}]}), encoding="utf-8")
    (job_dir / "words.json").write_text(json.dumps([{"word": "oi", "start": 0.0, "end": 0.5}]), encoding="utf-8")
    (job_dir / "narration.wav").write_bytes(b"audio")

    editor_state = {"composition": {"scenes": [{"text": "editada"}], "words": [{"word": "oi"}]}}
    save = await client.post(
        f"/api/v1/jobs/{job.id}/edit",
        headers=auth_headers(verified_user),
        json={"editor_state": editor_state},
    )
    composition = await client.get(f"/api/v1/jobs/{job.id}/composition", headers=auth_headers(verified_user))

    assert save.status_code == 200, "Editor state should save successfully."
    assert composition.status_code == 200, "Saved composition should be retrievable."
    assert composition.json()["editor_state"] == editor_state, "Composition should return the saved editor_state."


@pytest.mark.asyncio
async def test_edit_espelha_script_no_postgres(
    client, db_session, job_factory, verified_user, auth_headers, storage_dir
):
    """Split-brain (achado da revisao adversarial): j.script guardava o roteiro ORIGINAL
    para sempre; edicoes so iam pro script.json em disco. Fallbacks de get_job/list_jobs
    (inclusive a flag degraded) serviam versao velha pos-edicao/reboot."""
    original = {"scenes": [{"text": "scene 1"}], "llm_provider": "openrouter-free"}
    job = await job_factory(script=original, editor_state=None)
    job_dir = storage_dir / "jobs" / str(job.id)
    job_dir.mkdir(parents=True)
    (job_dir / "script.json").write_text(json.dumps(original), encoding="utf-8")

    editor_state = {"composition": {"scenes": [{"text": "cena reescrita pelo usuario"}]}}
    save = await client.post(
        f"/api/v1/jobs/{job.id}/edit",
        headers=auth_headers(verified_user),
        json={"editor_state": editor_state},
    )
    assert save.status_code == 200

    refreshed = await db_session.get(Job, job.id)
    await db_session.refresh(refreshed)
    assert (
        refreshed.script["scenes"][0]["text"] == "cena reescrita pelo usuario"
    ), "O Postgres deve espelhar o script editado (fim do split-brain DB vs disco)."
    # Metadado de qualidade sobrevive a edicao (flag degraded e historica por design).
    assert refreshed.script["llm_provider"] == "openrouter-free"


@pytest.mark.asyncio
async def test_composition_preserves_utf8_accents(
    client, db_session, job_factory, verified_user, auth_headers, storage_dir
):
    """Regressao: no Windows read_text() sem encoding le UTF-8 como cp1252 -> mojibake.

    O worker grava script.json/words.json em UTF-8; o composition tem de devolver os
    acentos intactos (Sério, São, até), nao 'SÃ©rio'/'SÃ£o'.
    """
    job = await job_factory(script={"scenes": [{"text": "placeholder"}]}, editor_state=None)
    job_dir = storage_dir / "jobs" / str(job.id)
    (job_dir / "media").mkdir(parents=True)
    texto = "Buracos negros podem parar o tempo. Sério. São cadáveres com gravidade extrema até a luz."
    (job_dir / "script.json").write_text(
        json.dumps({"title": "Curiosidades é ótimo demais", "scenes": [{"text": texto}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (job_dir / "words.json").write_text(
        json.dumps([{"word": "São", "start": 0.0, "end": 0.5}], ensure_ascii=False),
        encoding="utf-8",
    )

    response = await client.get(f"/api/v1/jobs/{job.id}/composition", headers=auth_headers(verified_user))

    assert response.status_code == 200
    data = response.json()
    assert data["script"]["scenes"][0]["text"] == texto, "Acentos UTF-8 devem voltar intactos (sem mojibake cp1252)."
    assert data["script"]["title"] == "Curiosidades é ótimo demais"
    assert data["words"][0]["word"] == "São"


@pytest.mark.asyncio
async def test_jobs_endpoint_falls_back_to_database_status_when_redis_is_empty(
    client, job_factory, verified_user, auth_headers
):
    job = await job_factory(status="completed")
    response = await client.get("/api/v1/jobs", headers=auth_headers(verified_user))

    assert response.status_code == 200, "Jobs list should succeed for authenticated users."
    listed = next(item for item in response.json() if item["job_id"] == str(job.id))
    assert listed["status"] == "completed", "Jobs list should fall back to persisted DB status when Redis has no entry."


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["edit", "render", "download"])
async def test_delivered_job_reports_artifact_unavailable_when_shared_storage_is_missing(
    operation, client, job_factory, verified_user, auth_headers
):
    """A DB row is not enough: a missing artifact is an operational 503, not an IDOR-like 404."""
    job = await job_factory(status="editable", script={"scenes": [{"text": "scene 1"}]})
    headers = auth_headers(verified_user)

    if operation == "edit":
        response = await client.post(
            f"/api/v1/jobs/{job.id}/edit",
            headers=headers,
            json={"editor_state": {"composition": {"scenes": [{"text": "editada"}]}}},
        )
    elif operation == "render":
        response = await client.post(f"/api/v1/jobs/{job.id}/render", headers=headers)
    else:
        response = await client.get(f"/api/v1/jobs/{job.id}/download", headers=headers)

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "O arquivo deste video esta temporariamente indisponivel. "
        "Tente novamente; se persistir, informe o codigo da solicitacao ao suporte."
    )


@pytest.mark.asyncio
async def test_foreign_key_constraints_block_orphan_jobs_and_purchases(db_session, verified_user):
    orphan_job = Job(user_id=verified_user.id, topic="x", style="educational", duration_target=45)
    orphan_purchase = CreditPurchase(
        user_id=verified_user.id,
        package_name="starter",
        credits_amount=10,
        price_brl=1990,
        mp_preference_id="pref_1",
        status="pending",
    )
    db_session.add_all([orphan_job, orphan_purchase])
    await db_session.commit()

    with pytest.raises(Exception):
        await db_session.execute(delete(User).where(User.id == verified_user.id))
        await db_session.commit()
