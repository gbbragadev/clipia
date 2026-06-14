"""Gera videos candidatos ao showcase via API local, parametrizado por nicho.

Le os temas/template/style de scripts/niches_seed.py. Worker e --pool=solo (1 video por vez),
entao processa serial. Apos cada candidato, sugere o comando de promocao.

Uso (stack rodando):
    python -m scripts.generate_showcase_batch --niche curiosidades --count 3
    python -m scripts.generate_showcase_batch --niche all --count 1   # 1 de cada nicho
Le credenciais de .admin-credentials.local.
"""

import argparse
import time
from pathlib import Path

import httpx

from scripts.niches_seed import NICHE_SEED

API = "http://127.0.0.1:8005"


def build_jobs(niche: str, count: int) -> list[tuple[str, str, str, str]]:
    """Retorna lista de (topic, style, template_id, niche)."""
    niches = list(NICHE_SEED) if niche == "all" else [niche]
    jobs: list[tuple[str, str, str, str]] = []
    for n in niches:
        seed = NICHE_SEED[n]
        for topic in seed["topics"][:count]:
            jobs.append((topic, seed["style"], seed["template"], n))
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="Gera candidatos de showcase por nicho.")
    parser.add_argument("--niche", required=True, help="slug do nicho ou 'all'")
    parser.add_argument("--count", type=int, default=3, help="quantos videos por nicho (default 3)")
    parser.add_argument("--duration", type=int, default=35, help="duracao alvo em segundos")
    args = parser.parse_args()

    if args.niche != "all" and args.niche not in NICHE_SEED:
        raise SystemExit(f"Nicho desconhecido: {args.niche}. Opcoes: all, {', '.join(NICHE_SEED)}")

    jobs_spec = build_jobs(args.niche, args.count)
    if not jobs_spec:
        raise SystemExit("Nada para gerar.")

    creds = Path(".admin-credentials.local").read_text(encoding="utf-8").splitlines()
    email = creds[0].split(":", 1)[1].strip()
    password = creds[1].split(":", 1)[1].strip()

    client = httpx.Client(base_url=API, timeout=30)
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"

    done: list[tuple[str, str, str]] = []  # (job_id, topic, niche)
    for topic, style, template, niche in jobs_spec:
        r = client.post(
            "/api/v1/generate",
            json={"topic": topic, "style": style, "duration_target": args.duration, "template_id": template},
        )
        r.raise_for_status()
        job_id = r.json()["job_id"]
        print(f"queued {job_id}  [{niche}] {topic}")
        while True:
            st = client.get(f"/api/v1/jobs/{job_id}/status").json()
            if st["status"] in ("completed", "editable"):
                print(f"  done: {job_id}")
                done.append((job_id, topic, niche))
                break
            if st["status"] in ("failed", "error"):
                print(f"  FAILED: {job_id}: {st.get('error')}")
                break
            time.sleep(10)

    print("\nCandidatos prontos (abra no editor, ajuste e promova):")
    for job_id, topic, niche in done:
        print(f"  editor:  http://localhost:3003/editor/{job_id}")
        print(f'  promote: python -m scripts.promote_to_showcase {job_id} {niche} "{topic}"')


if __name__ == "__main__":
    main()
