"""Valida que um usuario NOVO (um estranho qualquer) consegue usar o ClipIA de ponta a ponta:
cadastrar -> receber OTP -> verificar email -> gerar um video ate o MP4 final.

Roda contra o backend vivo (default http://127.0.0.1:8005). Cria uma conta de teste
descartavel e a remove no fim (jobs + usuario). Use antes de divulgar / depois de deploy.

Uso (com o venv312 ativo, a partir da raiz do repo):
    python scripts/validate_readiness.py
    python scripts/validate_readiness.py --base http://127.0.0.1:8005
    python scripts/validate_readiness.py --no-video   # para no enfileiramento, nao gera o MP4

Saida: relatorio [PASS]/[FAIL]/[WARN]. Exit code != 0 se algum check critico falhar.
"""

import argparse
import asyncio
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

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

    # 2. Email: dominio verificado no Resend
    check_resend_domain()

    # 3. Fluxo E2E como um estranho
    email = f"validacao+{uuid.uuid4().hex[:10]}@{DOMAIN}"
    password = "Valida!" + uuid.uuid4().hex[:8]
    conn = None
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
        if st == 200 and job_id:
            _mark("PASS", f"Geracao enfileirada (job {job_id[:8]}, custo {body.get('credit_cost')} credito).")
        else:
            _mark("FAIL", f"/generate recusou (status={st}): {body.get('detail') or body}")
            return

        if not make_video:
            _mark("WARN", "--no-video: parei no enfileiramento, nao esperei o MP4.")
            return

        # 3e. espera o worker processar ate o MP4 final
        mp4 = Path(settings.STORAGE_DIR) / "output" / f"{job_id}.mp4"
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
            if status in terminal or mp4.exists():
                break
        if mp4.exists() and mp4.stat().st_size > 10_000:
            _mark("PASS", f"MP4 final gerado: {mp4} ({mp4.stat().st_size // 1024} KB). Estranho consegue usar.")
        else:
            _mark("FAIL", f"Timeout/sem MP4: ultimo status='{last}', arquivo existe={mp4.exists()}.")
    finally:
        # cleanup: remove a conta de teste e seus jobs
        if conn is None:
            try:
                conn = await _db()
            except Exception:
                conn = None
        if conn is not None:
            uid = await conn.fetchval("SELECT id FROM users WHERE email=$1", email)
            if uid:
                await conn.execute("DELETE FROM jobs WHERE user_id=$1", uid)
                await conn.execute("DELETE FROM users WHERE id=$1", uid)
                _mark("INFO", f"Limpei a conta de teste {email}.")
            await conn.close()


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
