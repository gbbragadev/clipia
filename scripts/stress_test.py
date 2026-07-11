"""Stress test de concorrencia real do ClipIA: simula N usuarios novos fazendo o
funil completo (cadastro -> OTP -> verify -> /generate) EM PARALELO e mede como o
worker single-concurrency comporta a fila.

Cenario: o worker Celery roda com --concurrency=1 (1 video por vez em todo o
sistema, ver app/worker/celery_app.py). Este script prova isso na pratica e
mede:
  - latencia de fila (enqueue -> "running")
  - latencia total (enqueue -> MP4 pronto)
  - throughput (videos concluidos por minuto)
  - taxa de falha
  - ordem de processamento (prova a serializacao)

Roda contra producao (https://clipia.com.br) ou local. Cria contas descartaveis
com email stress+{uuid}@clipia.com.br e remove tudo no fim (jobs + users +
arquivos), mesmo em falha.

PRE-REQUISITOS:
  - READINESS_BYPASS_SECRET definido no .env (senao o Turnstile bloqueia o cadastro)
  - WELCOME_CREDIT_BONUS >= N (senao os usuarios entram sem credito p/ todos gerarem)
  - Worker + backend reiniciados com a build que voce quer testar

Uso (a partir da raiz do repo, com o venv ativo):
    python scripts/stress_test.py
    python scripts/stress_test.py --base https://clipia.com.br --users 5
    python scripts/stress_test.py --base http://127.0.0.1:8005 --users 8 --no-cleanup

Saida: tabela de latencias por usuario + veredito [PASS]/[WARN]/[FAIL].
Exit code != 0 se a taxa de falha for alta (>25%) ou se algum critico quebrar.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path

# raiz do repo no path para importar o app
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.config import settings  # noqa: E402

DOMAIN = "clipia.com.br"

# Template/voz mais baratos: 1 credito, nao toca APIs pagas (sem ElevenLabs/Seedance/gpt-image).
GEN_PAYLOAD = {
    "topic": "Tres curiosidades rapidas sobre o oceano profundo",
    "style": "educational",
    "duration_target": 15,
    "template_id": "stock_narration",
    "voice_provider": "edge",
}

TERMINAL_STATUSES = {"completed", "finished", "done", "editable", "finalized", "failed", "cancelled"}


@dataclass
class UserResult:
    """Resultado de UM usuario virtual no teste."""

    label: str
    email: str
    registered: bool = False
    verified: bool = False
    job_id: str | None = None
    enqueue_ok: bool = False
    enqueue_at: float | None = None
    running_at: float | None = None
    done_at: float | None = None
    final_status: str = ""
    error: str = ""

    @property
    def queue_latency(self) -> float | None:
        if self.enqueue_at and self.running_at:
            return self.running_at - self.enqueue_at
        return None

    @property
    def total_latency(self) -> float | None:
        if self.enqueue_at and self.done_at:
            return self.done_at - self.enqueue_at
        return None


@dataclass
class TestReport:
    users: list[UserResult] = field(default_factory=list)
    started_at: float = 0.0
    finished_at: float = 0.0

    @property
    def duration(self) -> float:
        return self.finished_at - self.started_at

    @property
    def completed(self) -> list[UserResult]:
        return [u for u in self.users if u.final_status in {"completed", "finished", "done", "editable", "finalized"}]

    @property
    def failed(self) -> list[UserResult]:
        return [u for u in self.users if u.final_status in {"failed", "cancelled"} or u.error]

    @property
    def success_rate(self) -> float:
        if not self.users:
            return 0.0
        return len(self.completed) / len(self.users)


def _http(
    method: str,
    url: str,
    body: dict | None = None,
    token: str | None = None,
    extra_headers: dict | None = None,
    timeout: int = 30,
) -> tuple[int, dict]:
    """Request JSON simples. Retorna (status, json|{}). Nao levanta em erro HTTP."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    # Cloudflare Bot Fight Mode bloqueia o UA padrao do Python — usar UA identificavel.
    req.add_header("User-Agent", "ClipIA-StressTest/1.0 (+https://clipia.com.br)")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    for k, v in (extra_headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode() or "{}"
            return r.status, json.loads(raw)
    except urllib.error.HTTPError as e:
        raw = e.read().decode() or "{}"
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {"detail": raw}
    except Exception as e:  # conexao recusada / timeout
        return 0, {"detail": str(e)}


async def _db():
    u = make_url(settings.DATABASE_URL)
    return await asyncpg.connect(host=u.host, port=u.port, user=u.username, password=u.password, database=u.database)


async def _register_and_verify(label: str, base_api: str, bypass_secret: str | None) -> tuple[UserResult, str | None]:
    """Cadastra + verifica email (lendo OTP do banco). Retorna (result, token|None)."""
    result = UserResult(label=label, email=f"stress+{label}@{DOMAIN}")
    conn = None
    try:
        bypass_headers = {"X-Readiness-Bypass": bypass_secret} if bypass_secret else {}
        st, body = _http(
            "POST",
            f"{base_api}/auth/register",
            {"email": result.email, "name": f"Stress {label}", "password": "Stress!" + uuid.uuid4().hex[:8]},
            extra_headers=bypass_headers,
        )
        token = body.get("access_token")
        if st != 201 or not token:
            result.error = f"register falhou ({st}): {body.get('detail')}"
            return result, None
        result.registered = True

        # Le o OTP do banco (mesmo truque do validate_readiness.py: o email e so para humanos).
        conn = await _db()
        code = await conn.fetchval("SELECT verification_code FROM users WHERE email=$1", result.email)
        if not code:
            result.error = "OTP nao gerado apos cadastro"
            return result, None

        st, body = _http("POST", f"{base_api}/auth/verify-email", {"email": result.email, "code": code})
        if st != 200:
            result.error = f"verify-email falhou ({st}): {body.get('detail')}"
            return result, None
        result.verified = True
        return result, token
    finally:
        if conn:
            await conn.close()


async def _enqueue_and_track(result: UserResult, token: str, base_api: str) -> UserResult:
    """Dispara /generate e acompanha o job ate terminal. Preenche latencias."""
    result.enqueue_at = time.monotonic()
    st, body = _http("POST", f"{base_api}/generate", GEN_PAYLOAD, token=token)
    result.job_id = body.get("job_id")
    if st != 200 or not result.job_id:
        result.error = f"/generate falhou ({st}): {body.get('detail') or body}"
        return result
    result.enqueue_ok = True

    # Poll ate terminal. Intervalo de 3s (mesmo validate_readiness.py).
    last_status = ""
    for _ in range(300):  # ate ~15min por job
        await asyncio.sleep(3)
        st, body = _http("GET", f"{base_api}/jobs/{result.job_id}", token=token)
        status = body.get("status", "?")
        # Marca o momento em que saiu da fila e comecou a rodar.
        if result.running_at is None and status in {"running", "processing", "in_progress"}:
            result.running_at = time.monotonic()
        if status != last_status:
            print(f"    [{result.label}] {status} {int(body.get('progress', 0))}%".rstrip())
            last_status = status
        if status in TERMINAL_STATUSES:
            result.final_status = status
            result.done_at = time.monotonic()
            if status == "failed":
                result.error = body.get("error") or "job falhou sem detalhe"
            break
    else:
        result.final_status = "timeout"
        result.error = f"job nao terminou em ~15min (ultimo status={last_status})"
        result.done_at = time.monotonic()
    return result


async def _run_user(label: str, base_api: str, bypass_secret: str | None) -> UserResult:
    """Pipeline completo de 1 usuario virtual."""
    result, token = await _register_and_verify(label, base_api, bypass_secret)
    if not token:
        return result
    return await _enqueue_and_track(result, token, base_api)


async def _cleanup(users: list[UserResult]) -> None:
    """Remove todas as contas de teste + seus jobs. Idempotente, segura para chamar 2x."""
    conn = None
    try:
        conn = await _db()
        for u in users:
            if not u.email:
                continue
            uid = await conn.fetchval("SELECT id FROM users WHERE email=$1", u.email)
            if uid:
                await conn.execute("DELETE FROM jobs WHERE user_id=$1", uid)
                await conn.execute("DELETE FROM users WHERE id=$1", uid)
        cleaned = sum(1 for u in users if u.email)
        print(f"\n[cleanup] {cleaned} conta(s) de teste removida(s).")
    except Exception as e:
        print(f"\n[cleanup] AVISO: falha ao limpar ({e}); remova manualmente os emails 'stress+*@{DOMAIN}'.")
    finally:
        if conn:
            await conn.close()


def _print_report(report: TestReport, target_users: int) -> int:
    """Imprime relatorio final. Retorna exit code (0=ok, 1=falha critica)."""
    print("\n" + "=" * 70)
    print("RELATORIO DE STRESS TEST")
    print("=" * 70)
    print(f"Usuarios alvo:        {target_users}")
    print(f"Duracao total:        {report.duration:.0f}s ({report.duration / 60:.1f} min)")

    completed = report.completed
    failed = report.failed

    print(f"Concluidos com sucesso: {len(completed)}/{target_users}")
    print(f"Falhos:                {len(failed)}/{target_users}")
    print(f"Taxa de sucesso:       {report.success_rate * 100:.0f}%")

    if completed:
        # Latencias
        queue_lats = [u.queue_latency for u in completed if u.queue_latency is not None]
        total_lats = [u.total_latency for u in completed if u.total_latency is not None]
        if queue_lats:
            print("\nLatencia de FILA (enqueue -> running):")
            print(
                f"  min {min(queue_lats):.0f}s | mediana {statistics.median(queue_lats):.0f}s | "
                f"max {max(queue_lats):.0f}s | media {statistics.mean(queue_lats):.0f}s"
            )
        if total_lats:
            print("\nLatencia TOTAL (enqueue -> MP4 pronto):")
            print(
                f"  min {min(total_lats):.0f}s | mediana {statistics.median(total_lats):.0f}s | "
                f"max {max(total_lats):.0f}s | media {statistics.mean(total_lats):.0f}s"
            )
        if report.duration > 0:
            tput = len(completed) / (report.duration / 60)
            print(f"\nThroughput efetivo: {tput:.1f} videos/min")

        # Prova de serializacao: ordena por running_at e mostra a diferenca entre consecutivos.
        ordered = sorted([u for u in completed if u.running_at], key=lambda u: u.running_at)
        if len(ordered) >= 2:
            gaps = [ordered[i + 1].running_at - ordered[i].running_at for i in range(len(ordered) - 1)]
            print("\nOrdem de processamento (confirma serializacao do worker):")
            print(
                f"  gap entre videos consecutivos: min {min(gaps):.0f}s | "
                f"media {statistics.mean(gaps):.0f}s | max {max(gaps):.0f}s"
            )
            order_str = " -> ".join(u.label for u in ordered)
            print(f"  ordem: {order_str}")

    # Tabela por usuario
    print("\nDetalhe por usuario:")
    print(f"  {'usuario':<12} {'status':<12} {'fila':>8} {'total':>8}  {'erro'}")
    for u in report.users:
        q = f"{u.queue_latency:.0f}s" if u.queue_latency else "-"
        t = f"{u.total_latency:.0f}s" if u.total_latency else "-"
        err = (u.error[:40] + "...") if len(u.error) > 40 else u.error
        print(f"  {u.label:<12} {u.final_status or '-':<12} {q:>8} {t:>8}  {err}")

    # Veredito
    print("\n" + "-" * 70)
    if not completed and failed:
        print("VEREDITO: [FAIL] Nenhum video concluido. Worker/Backend com problema.")
        return 1
    if report.success_rate < 0.75:
        print(
            f"VEREDITO: [FAIL] Taxa de sucesso baixa ({report.success_rate * 100:.0f}%). "
            "Investigar falhas antes de abrir para testadores."
        )
        return 1
    if completed and total_lats and max(total_lats) > 600:
        print(
            f"VEREDITO: [WARN] {len(completed)}/{target_users} ok, mas latencia maxima "
            f"{max(total_lats):.0f}s > 10min. Fila pode ser lenta para testadores; "
            "considere subir worker_concurrency=2."
        )
        return 0
    print(
        f"VEREDITO: [PASS] {len(completed)}/{target_users} videos concluidos, "
        f"taxa de sucesso {report.success_rate * 100:.0f}%."
    )
    if target_users >= 8:
        print("         (Para 8+ usuarios simultaneos, monitore /metrics durante o uso real dos testadores.)")
    return 0


async def run(base: str, users: int, cleanup: bool) -> int:
    base = base.rstrip("/")
    base_api = f"{base}/api/v1"

    # 1. Backend vivo?
    st, _ = _http("GET", f"{base}/health")
    if st != 200:
        print(f"[FAIL] Backend /health nao respondeu 200 (status={st}). Suba o backend antes.")
        return 1
    print(f"[PASS] Backend /health respondeu em {base}.")

    # 2. Bypass do Turnstile disponivel?
    bypass = settings.READINESS_BYPASS_SECRET
    if not bypass:
        print("[WARN] READINESS_BYPASS_SECRET vazio: Turnstile vai bloquear o cadastro em prod.")
        print("       Sete no .env e reinicie o backend, ou rode contra localhost.")
        # Nao aborta: contra localhost (dev) o Turnstile costuma estar desligado.

    # 3. Crédito suficiente? Cada usuario precisa de 1 credito (template Edge).
    bonus = settings.WELCOME_CREDIT_BONUS
    if bonus < 1:
        print("[FAIL] WELCOME_CREDIT_BONUS < 1: os usuarios de teste nao terao credito p/ gerar.")
        return 1
    if bonus < users:
        print(f"[WARN] WELCOME_CREDIT_BONUS={bonus} < {users} usuarios: cada um so gera {bonus} video(s).")
    else:
        print(f"[PASS] WELCOME_CREDIT_BONUS={bonus} (cada tester tera credito para >=1 video).")

    print(f"\nDisparando {users} usuarios virtuais em paralelo...\n")

    report = TestReport(started_at=time.monotonic())
    labels = [f"u{i+1:02d}" for i in range(users)]
    try:
        # asyncio.gather roda todos os N usuarios concorrentemente. O worker serializa a fila.
        report.users = await asyncio.gather(*[_run_user(lbl, base_api, bypass) for lbl in labels])
    except KeyboardInterrupt:
        print("\n[WARN] Interrompido pelo usuario. Limpando contas de teste...")
    finally:
        report.finished_at = time.monotonic()
        if cleanup:
            await _cleanup(report.users)

    return _print_report(report, users)


def main() -> None:
    p = argparse.ArgumentParser(description="Stress test de concorrencia real do ClipIA.")
    p.add_argument("--base", default="http://127.0.0.1:8005", help="URL base do backend (default: localhost:8005)")
    p.add_argument("--users", type=int, default=5, help="Numero de usuarios virtuais simultaneos (default: 5)")
    p.add_argument("--no-cleanup", action="store_true", help="Nao remove as contas de teste (debug)")
    args = p.parse_args()

    if args.users < 1:
        print("--users deve ser >= 1.")
        sys.exit(2)
    if args.users > 15:
        print(
            "[!] Mais de 15 usuarios simultaneos pode saturar o worker single-concurrency "
            "e gerar timeouts. Abortando por seguranca."
        )
        sys.exit(2)
    if args.users > 10:
        print(
            f"[!] Atencao: {args.users} usuarios num worker concurrency=1 significa fila longa. "
            f"Use somente se souber o que esta fazendo."
        )

    print(f"== Stress Test ClipIA -> {args.base} | {args.users} usuarios ==\n")
    exit_code = asyncio.run(run(args.base, args.users, cleanup=not args.no_cleanup))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
