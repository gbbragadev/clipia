"""Gera videos candidatos ao showcase via API local (batch).

Uso (stack rodando):
    python -m scripts.generate_showcase_batch
Le credenciais de .admin-credentials.local. Gera 1 job por tema e acompanha ate concluir.
"""

import time
from pathlib import Path

import httpx

API = "http://127.0.0.1:8005"

# (topic, style, template_id, duration, niche-alvo p/ manifesto)
BATCH = [
    ("5 curiosidades sobre o oceano profundo", "educational", "stock_narration", 35, "educational"),
    ("Por que os gatos ronronam? A ciencia explica", "educational", "stock_narration", 30, "educational"),
    ("3 habitos que destroem sua produtividade", "educational", "stock_narration", 30, "tips"),
    ("Como economizar dinheiro sem perceber", "educational", "stock_narration", 30, "tips"),
    ("A historia do cafe: da Etiopia ao mundo", "storytelling", "stock_narration", 40, "story"),
    ("O misterio do navio que sumiu em 1872", "storytelling", "novelinha_historica", 40, "story"),
    ("Fatos absurdos que parecem mentira", "comedy", "stock_narration", 30, "entertainment"),
    ("O que aconteceria se a internet caisse no mundo todo", "news", "stock_narration", 35, "entertainment"),
]


def main() -> None:
    creds = Path(".admin-credentials.local").read_text(encoding="utf-8").splitlines()
    email = creds[0].split(":", 1)[1].strip()
    password = creds[1].split(":", 1)[1].strip()

    client = httpx.Client(base_url=API, timeout=30)
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"

    jobs: list[tuple[str, str]] = []
    for topic, style, template, duration, niche in BATCH:
        r = client.post(
            "/api/v1/generate",
            json={"topic": topic, "style": style, "duration_target": duration, "template_id": template},
        )
        r.raise_for_status()
        job_id = r.json()["job_id"]
        jobs.append((job_id, topic))
        print(f"queued {job_id}  [{niche}] {topic}")
        # worker e --pool=solo: 1 por vez; aguardar concluir antes do proximo
        while True:
            st = client.get(f"/api/v1/jobs/{job_id}/status").json()
            if st["status"] in ("completed", "editable"):
                print(f"  done: {job_id}")
                break
            if st["status"] in ("failed", "error"):
                print(f"  FAILED: {job_id}: {st.get('error')}")
                break
            time.sleep(10)

    print("\nCandidatos prontos:")
    for job_id, topic in jobs:
        print(f"  http://localhost:3003/editor/{job_id}  <- {topic}")


if __name__ == "__main__":
    main()
