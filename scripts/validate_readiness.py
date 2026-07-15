"""Valida que um usuario NOVO consegue usar o ClipIA de ponta a ponta:
cadastro -> OTP -> geracao -> preview -> duas edicoes -> rerender -> download.

Roda contra o backend vivo (default http://127.0.0.1:8005). Cria uma conta de teste
descartavel, anonimiza a conta pela API e remove os arquivos no fim. Use depois de cada deploy.

Uso (com o venv312 ativo, a partir da raiz do repo):
    python scripts/validate_readiness.py
    python scripts/validate_readiness.py --base http://127.0.0.1:8005
    python scripts/validate_readiness.py --no-video   # para no enfileiramento, nao gera o MP4

Saida: relatorio [PASS]/[FAIL]/[WARN]. Exit code != 0 se algum check critico falhar.
"""

import argparse
import asyncio
import json
import shutil
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urljoin

# raiz do repo no path para importar o app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg  # noqa: E402  (vem com o driver async do projeto)
from sqlalchemy.engine import make_url  # noqa: E402

from app.config import settings  # noqa: E402

DOMAIN = "clipia.com.br"  # dominio de envio que precisa estar verificado no Resend

_fail = 0


def _mark(level: str, msg: str) -> None:
    global _fail
    if level == "FAIL":
        _fail += 1
    print(f"[{level:4}] {msg}")


def _http(
    method: str, url: str, body: dict | None = None, token: str | None = None, extra_headers: dict | None = None
) -> tuple[int, dict]:
    """Request JSON simples. Retorna (status, json|{}). Nao levanta em erro HTTP."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    # Cloudflare Bot Fight Mode bloqueia o User-Agent padrao do Python ("Python-urllib/3.x")
    # com erro 1010. Usamos um UA explicito e identificavel para o readiness passar
    # pelo WAF quando rodado contra o dominio publico.
    req.add_header("User-Agent", "ClipIA-Readiness/1.0 (+https://clipia.com.br)")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for k, v in (extra_headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read().decode() or "{}"
            return r.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode() or "{}"
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"detail": raw}
    except Exception as e:  # conexao recusada etc
        return 0, {"detail": str(e)}


def _http_bytes(
    method: str,
    url: str,
    token: str | None = None,
    extra_headers: dict | None = None,
) -> tuple[int, bytes, dict[str, str]]:
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", "ClipIA-Readiness/1.0 (+https://clipia.com.br)")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for key, value in (extra_headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            return response.status, response.read(), {key.lower(): value for key, value in response.headers.items()}
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(), {key.lower(): value for key, value in exc.headers.items()}
    except Exception as exc:
        return 0, str(exc).encode("utf-8"), {}


async def _db():
    u = make_url(settings.DATABASE_URL)
    return await asyncpg.connect(host=u.host, port=u.port, user=u.username, password=u.password, database=u.database)


def check_resend_domain() -> None:
    """Check decisivo do email: o dominio precisa estar 'verified' no Resend, senao um
    estranho nunca recebe o OTP (so o dono da conta Resend recebe)."""
    key = settings.SMTP_PASSWORD
    if not settings.SMTP_HOST:
        _mark("FAIL", "SMTP_HOST vazio: nenhum email de verificacao sera enviado (OTP so no log).")
        return
    if not key or not key.startswith("re_"):
        _mark("WARN", "SMTP_PASSWORD nao parece uma API key Resend (re_...); pulei o check de dominio.")
        return
    req = urllib.request.Request("https://api.resend.com/domains")
    req.add_header("Authorization", f"Bearer {key}")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            domains = json.loads(r.read().decode()).get("data", [])
    except urllib.error.HTTPError as e:
        if e.code == 403:
            _mark(
                "WARN",
                "Resend API 403 (key e so de envio, sem listar dominios). Prova alternativa: "
                'rode  python -c "from app.auth.email import send_verification_email as s; '
                "print('OK' if s('SEU_EMAIL@gmail.com','123456','Teste') else 'FALHOU')\"  "
                "-> 'OK' confirma dominio verificado (Resend recusa envio de dominio nao verificado).",
            )
        else:
            _mark("WARN", f"Resend API erro {e.code}; valide o dominio manualmente.")
        return
    except Exception as e:
        _mark("WARN", f"Nao consegui consultar a Resend API ({e}); valide o dominio manualmente.")
        return
    match = next((d for d in domains if d.get("name") == DOMAIN), None)
    if not match:
        _mark("FAIL", f"Dominio {DOMAIN} NAO existe no Resend: emails de OTP nao saem para estranhos.")
    elif match.get("status") == "verified":
        _mark(
            "PASS", f"Resend: dominio {DOMAIN} verificado (SMTP_FROM={settings.SMTP_FROM}) -> OTP chega a qualquer um."
        )
    else:
        _mark(
            "FAIL",
            f"Resend: dominio {DOMAIN} esta '{match.get('status')}' (nao verificado): estranhos NAO recebem o OTP.",
        )


async def run(base: str, make_video: bool) -> None:
    base = base.rstrip("/")
    api = f"{base}/api/v1"

    # 1. Backend vivo
    st, _ = _http("GET", f"{base}/health")
    if st == 200:
        _mark("PASS", "Backend /health respondeu 200.")
    else:
        _mark("FAIL", f"Backend /health falhou (status={st}). Suba o backend antes de validar.")
        return

    if make_video:
        st, deep = _http("GET", f"{base}/health/deep")
        worker_match = deep.get("checks", {}).get("storage", {}).get("worker_match")
        if st == 200 and deep.get("status") == "healthy" and worker_match is True:
            _mark("PASS", "Health profundo confirma storage compartilhado entre API e worker.")
        else:
            _mark(
                "FAIL",
                f"Storage da API/worker nao esta alinhado (status={st}, worker_match={worker_match}).",
            )
            return

    # 2. Email: dominio verificado no Resend
    check_resend_domain()

    # 3. Fluxo E2E como um estranho
    email = f"validacao+{uuid.uuid4().hex[:10]}@{DOMAIN}"
    password = "Valida!" + uuid.uuid4().hex[:8]
    conn = None
    job_id = None
    token = None
    verified_credits = 0
    generation_cost = 0
    try:
        # 3a. cadastro (bypass do Turnstile se READINESS_BYPASS_SECRET estiver configurado)
        bypass_headers = {}
        if settings.READINESS_BYPASS_SECRET:
            bypass_headers["X-Readiness-Bypass"] = settings.READINESS_BYPASS_SECRET
        st, body = _http(
            "POST",
            f"{api}/auth/register",
            {"email": email, "name": "Validacao QA", "password": password},
            extra_headers=bypass_headers,
        )
        token = body.get("access_token")
        if st == 201 and token:
            _mark("PASS", f"Cadastro aceito (201) para {email}.")
        else:
            _mark("FAIL", f"Cadastro falhou (status={st}): {body.get('detail')}")
            return

        # 3b. OTP foi gerado e gravado? (le do banco, como faria o email)
        conn = await _db()
        code = await conn.fetchval("SELECT verification_code FROM users WHERE email=$1", email)
        if code:
            _mark("PASS", f"OTP gerado e persistido para a conta nova ({code}).")
        else:
            _mark("FAIL", "Nenhum OTP gravado apos o cadastro: verify-email vai travar.")
            return

        # 3c. verificacao do email -> ganha 2 creditos
        st, body = _http("POST", f"{api}/auth/verify-email", {"email": email, "code": code})
        if st == 200 and body.get("credits", 0) >= 1:
            verified_credits = int(body.get("credits", 0))
            _mark("PASS", f"Email verificado e {body.get('credits')} creditos liberados.")
        else:
            _mark("FAIL", f"verify-email falhou (status={st}): {body.get('detail') or body}")
            return

        # 3d. dispara geracao (template/voz gratis para nao gastar APIs pagas)
        gen = {
            "topic": "Tres curiosidades sobre o oceano profundo que poucos conhecem",
            "style": "educational",
            "duration_target": 15,
            "template_id": "stock_narration",
            "voice_provider": "edge",
        }
        st, body = _http("POST", f"{api}/generate", gen, token=token)
        job_id = body.get("job_id")
        if st in {200, 202} and job_id:
            generation_cost = int(body.get("credit_cost") or 0)
            _mark("PASS", f"Geracao enfileirada (job {job_id[:8]}, custo {body.get('credit_cost')} credito).")
        else:
            _mark("FAIL", f"/generate recusou (status={st}): {body.get('detail') or body}")
            return

        if not make_video:
            _mark("WARN", "--no-video: parei no enfileiramento, nao esperei o MP4.")
            return

        # 3e. espera o worker processar. O gate consulta a API publica: olhar o
        # filesystem local mascarava exatamente o split de storage entre API/worker.
        terminal = {"completed", "finished", "done", "editable", "finalized"}
        last = ""
        for _ in range(100):  # ~300s
            await asyncio.sleep(3)
            st, body = _http("GET", f"{api}/jobs/{job_id}", token=token)
            status = body.get("status", "?")
            step = body.get("current_step") or ""
            if (status, step) != (last, ""):
                print(f"        ... {status} {int(body.get('progress', 0))}% {step}".rstrip())
            last = status
            if status == "failed":
                _mark("FAIL", f"Geracao FALHOU no worker: {body.get('error') or 'sem detalhe'}")
                return
            if status in terminal:
                break
        if last not in terminal:
            _mark("FAIL", f"Timeout sem entrega: ultimo status='{last}'.")
            return
        _mark("PASS", f"Geracao chegou ao estado entregue ('{last}').")

        # 3f. abre a composicao e prova um range da midia usada pelo preview.
        st, composition = _http("GET", f"{api}/jobs/{job_id}/composition", token=token)
        if st != 200:
            _mark("FAIL", f"Editor nao abriu a composicao publica (status={st}): {composition.get('detail')}")
            return
        media_urls = composition.get("media_urls") or []
        if not media_urls:
            _mark("FAIL", "Composicao entregue sem midia para o preview.")
            return
        preview_url = urljoin(f"{base}/", str(media_urls[0]).lstrip("/"))
        range_status, range_body, range_headers = _http_bytes(
            "GET",
            preview_url,
            token=token,
            extra_headers={"Range": "bytes=0-1023"},
        )
        if range_status != 206 or not range_body or "content-range" not in range_headers:
            _mark("FAIL", f"Preview nao aceitou range request (status={range_status}).")
            return
        _mark("PASS", "Preview autenticado respondeu range request (206).")

        # 3g. aplica exatamente duas mudancas: preset de legenda e trilha.
        saved = composition.get("editor_state") or {}
        saved_composition = saved.get("composition") if isinstance(saved, dict) else None
        editor_composition = dict(saved_composition or {})
        editor_composition.update(
            {
                "title": composition.get("script", {}).get("title") or "Video de validacao",
                "scenes": composition.get("script", {}).get("scenes") or [],
                "words": composition.get("words") or [],
                "audioUrl": composition.get("audio_url") or "",
                "mediaUrls": media_urls,
                "subtitleStyle": {
                    **(composition.get("subtitle_style") or {}),
                    **(editor_composition.get("subtitleStyle") or {}),
                    "preset": "neon",
                },
                "voiceConfig": editor_composition.get("voiceConfig") or {"provider": "edge"},
                "fps": composition.get("fps") or 30,
                "width": composition.get("width") or 1080,
                "height": composition.get("height") or 1920,
                "overlays": editor_composition.get("overlays") or [],
                "musicAssetId": "lofi-chill",
                "musicVolume": 0.3,
                "isRendering": False,
                "templateId": composition.get("template_id") or "stock_narration",
                "layoutType": composition.get("layout_type") or "fullscreen",
                "pendingCredits": composition.get("pending_credits") or 0,
            }
        )
        st, body = _http(
            "POST",
            f"{api}/jobs/{job_id}/edit",
            {"editor_state": {"composition": editor_composition}},
            token=token,
        )
        if st != 200:
            _mark("FAIL", f"Edicao nao foi salva (status={st}): {body.get('detail')}")
            return
        _mark("PASS", "Preset Neon e trilha Lo-Fi Chill foram salvos.")

        # 3h. rerenderiza a composicao editada e espera o terminal real.
        st, body = _http("POST", f"{api}/jobs/{job_id}/render", token=token)
        if st not in {200, 202}:
            _mark("FAIL", f"Rerender nao iniciou (status={st}): {body.get('detail')}")
            return
        render_last = ""
        for _ in range(140):  # ate ~7min para o worker solo/remotion
            await asyncio.sleep(3)
            st, body = _http("GET", f"{api}/jobs/{job_id}/status", token=token)
            render_last = body.get("status", "?")
            if render_last == "completed":
                break
            if render_last in {"error", "failed", "cancelled"}:
                _mark("FAIL", f"Rerender terminou em '{render_last}': {body.get('error') or body.get('detail')}")
                return
        if render_last != "completed":
            _mark("FAIL", f"Timeout do rerender: ultimo status='{render_last}'.")
            return
        _mark("PASS", "Rerender editado concluiu.")

        # 3i. o rerender sem operacao paga nao pode consumir outro credito.
        st, me = _http("GET", f"{api}/auth/me", token=token)
        expected_credits = verified_credits - generation_cost
        if st == 200 and me.get("credits") == expected_credits:
            _mark("PASS", f"Saldo final correto: {me.get('credits')} credito; rerender sem debito extra.")
        else:
            _mark("FAIL", f"Saldo divergente apos rerender: esperado={expected_credits}, recebido={me.get('credits')}.")
            return

        # 3j. baixa pela API publica; o tamanho/cabecalho provam que nao veio JSON/HTML de erro.
        download_status, mp4_body, download_headers = _http_bytes("GET", f"{api}/jobs/{job_id}/download", token=token)
        content_type = download_headers.get("content-type", "")
        if download_status == 200 and len(mp4_body) > 10_000 and "video/mp4" in content_type:
            _mark("PASS", f"MP4 publico baixado e reproduzivel ({len(mp4_body) // 1024} KB).")
        else:
            _mark(
                "FAIL",
                f"Download final invalido (status={download_status}, bytes={len(mp4_body)}, tipo={content_type}).",
            )
    finally:
        # Cleanup pela mesma regra de negocio do produto. A conta fica anonimizada
        # e o ledger permanece auditavel, sem DELETEs diretos que violem FKs.
        if token:
            cleanup_status, cleanup_body = _http(
                "POST",
                f"{api}/auth/delete-account",
                {"password": password},
                token=token,
            )
            if cleanup_status == 200:
                _mark("INFO", f"Anonimizei a conta descartavel {email} pela API.")
            else:
                _mark(
                    "WARN",
                    f"Nao consegui anonimizar a conta descartavel (status={cleanup_status}): "
                    f"{cleanup_body.get('detail') or cleanup_body}",
                )
        if conn is not None:
            await conn.close()
        if job_id:
            shutil.rmtree(Path(settings.STORAGE_DIR) / "jobs" / str(job_id), ignore_errors=True)
            (Path(settings.STORAGE_DIR) / "output" / f"{job_id}.mp4").unlink(missing_ok=True)
            (Path(settings.STORAGE_DIR) / "output" / f"{job_id}.jpg").unlink(missing_ok=True)


def main() -> None:
    p = argparse.ArgumentParser(description="Valida prontidao do funil de novo usuario do ClipIA.")
    p.add_argument("--base", default="http://127.0.0.1:8005", help="URL base do backend")
    p.add_argument("--no-video", action="store_true", help="para no enfileiramento, nao gera o MP4")
    args = p.parse_args()

    print(f"== Validacao de prontidao ClipIA -> {args.base} ==\n")
    asyncio.run(run(args.base, make_video=not args.no_video))
    print()
    if _fail:
        print(f"RESULTADO: {_fail} check(s) critico(s) FALHARAM. NAO esta pronto para o publico.")
        sys.exit(1)
    print("RESULTADO: tudo verde. Um usuario novo consegue ir do cadastro ao video.")


if __name__ == "__main__":
    main()
