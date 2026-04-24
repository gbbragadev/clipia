"""Phase B smoke test — gera 1 video end-to-end via template novelinha_historica.

Usa quality=low para custo baixo (~$0.03). Requer:
  - Backend running: uvicorn app.main:app --port 8005
  - Worker running: celery -A app.worker.celery_app worker -l info --pool=solo
  - OPENAI_API_KEY, ELEVENLABS_API_KEY, ANTHROPIC_API_KEY nas env vars
  - Voice id valido colocado em app/templates.py (substituir TODO_VOICE_ID)

Uso:
    python scripts/test-phase-b-smoke.py "O Inquilino do Quarto 337"
"""

from __future__ import annotations

import os
import sys
import time

import requests

BACKEND = os.environ.get("BACKEND_URL", "http://127.0.0.1:8005")


def login() -> str:
    email = os.environ.get("ADMIN_EMAIL", "gbbraga.dev@gmail.com")
    with open(".admin-credentials.local", "r", encoding="utf-8") as f:
        pwd_line = next(line for line in f if line.startswith("password"))
    password = pwd_line.split("=", 1)[1].strip().strip('"')

    r = requests.post(f"{BACKEND}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    r.raise_for_status()
    return r.json()["token"]


def create_job(token: str, topic: str) -> str:
    r = requests.post(
        f"{BACKEND}/api/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "topic": topic,
            "style": "dramatico cinematografico",
            "duration_target": 30,
            "template_id": "novelinha_historica",
            "voice_provider": "elevenlabs",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["id"]


def wait_job(token: str, job_id: str, timeout_s: int = 240) -> dict:
    start = time.monotonic()
    while time.monotonic() - start < timeout_s:
        r = requests.get(
            f"{BACKEND}/api/jobs/{job_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        print(f"  status={data['status']} step={data.get('current_step')} detail={data.get('detail')}")
        if data["status"] in {"editable", "completed", "failed", "cancelled"}:
            return data
        time.sleep(3)
    raise TimeoutError(f"job {job_id} nao terminou em {timeout_s}s")


def main() -> int:
    topic = sys.argv[1] if len(sys.argv) > 1 else "O hospede que nunca saiu do quarto 337"
    os.environ.setdefault("GPT_IMAGE_QUALITY", "low")

    token = login()
    print("[+] Autenticado.")
    jid = create_job(token, topic)
    print(f"[+] Job criado: {jid}")
    result = wait_job(token, jid)
    print(f"[+] Resultado: {result['status']}")
    if result["status"] == "editable":
        print(f"[+] Video em: storage/output/{jid}.mp4")
        return 0
    print(f"[!] Erro: {result.get('error')}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
