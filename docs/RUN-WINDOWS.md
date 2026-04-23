# Rodando ClipIA no Windows

Este doc documenta o setup **exato** usado no PC do Gui em 2026-04-22
(Windows 11, GTX 1660 4GB, Python 3.12 no PATH, Node 24, Docker Desktop,
FFmpeg 8.1 no PATH).

## 1. Pre-requisitos

Software:
- Python 3.12 instalado em `C:\Users\<user>\AppData\Local\Programs\Python\Python312\`
  (winget install --id Python.Python.3.12 --silent --scope user). O path exato
  foi salvo na env var `CLIPIA_PYTHON312_EXE`.
- Node 24+ (`node --version`)
- Docker Desktop rodando
- FFmpeg 8+ no PATH (`ffmpeg -version`)
- Git

Env vars de User (Painel de Controle > Variaveis de ambiente > do usuario):
- `ANTHROPIC_API_KEY` — Claude
- `GROQ_API_KEY` — https://console.groq.com
- `OPENAI_API_KEY` — sk-proj-... (alias de OPEN_API_CLIPIA_TOKEN)
- `ELEVENLABS_API_KEY` — (alias de ELEVEN_LABS_CLIPIA_KEY)
- `PEXELS_API_KEY` — https://www.pexels.com/api
- `CLOUDFLARE_API_TOKEN`

Validar:
```powershell
.\scripts\check-env.ps1
```

## 2. Setup inicial (uma unica vez)

```powershell
# clone
git clone <url> auto-shorts
cd auto-shorts

# venv Python 3.12
& $env:CLIPIA_PYTHON312_EXE -m venv .venv312
.\.venv312\Scripts\Activate.ps1
pip install --upgrade pip
pip install -e ".[dev]"
pre-commit install

# infra
docker compose up postgres redis -d

# migrations
alembic upgrade head

# admin (idempotente)
python scripts/seed_admin.py
# guardar senha do .admin-credentials.local em gerenciador de senhas

# frontend deps
cd frontend
npm install
cd ..
```

## 3. Dia-a-dia dev

```powershell
.\scripts\start-all.ps1
```

Abre 3 janelas PowerShell (backend, worker, frontend). Para parar, fechar as
3 janelas (ou Ctrl+C em cada).

URLs locais:
- http://localhost:3003 — frontend
- http://localhost:8005/docs — Swagger backend

## 4. Tunnel Cloudflare (acesso externo)

```powershell
cloudflared tunnel run clipia-windows
```

Mapeamento (arquivo `~\.cloudflared\config.yml` ou via dashboard):
- `autoshorts.gbbragadev.com` -> `http://localhost:3003`
- `api-autoshorts.gbbragadev.com` -> `http://localhost:8005`

Setup inicial do tunnel — ver Task Scheduler ou servico Windows (Task 17 do plano).

## 5. Backup manual e restore

Backup:
```powershell
.\scripts\backup-postgres.ps1
```

Produz `storage\backups\clipia_YYYY-MM-DD_HHMM.sql.gz`. Retencao 14 dias.

Restore (em caso de desastre):
```powershell
# descomprimir
& "C:\Program Files\7-Zip\7z.exe" e storage\backups\clipia_2026-04-22_0300.sql.gz -o storage\backups\
docker compose up postgres -d
Get-Content storage\backups\clipia_2026-04-22_0300.sql | `
    docker exec -i auto-shorts-postgres-1 psql -U clipia -d clipia
```

## 6. Troubleshooting

**Celery worker nao aceita tasks:**
Em Windows, default do pool prefork nao funciona. O `start-all.ps1` ja passa
`--pool=solo`. Se rodar celery manual, lembrar:
```powershell
celery -A app.worker.celery_app worker -l info --concurrency=1 --pool=solo
```

**Erro "GROQ_API_KEY not configured":**
Env var nao foi herdada. Fechar e abrir novo PowerShell. Ou setar na sessao:
```powershell
$env:GROQ_API_KEY = [Environment]::GetEnvironmentVariable('GROQ_API_KEY','User')
```

**Postgres nao sobe:**
```powershell
docker compose logs postgres | Select-Object -Last 40
```

**JWT invalido no login:**
Usuario provavelmente foi criado com JWT_SECRET diferente. Rodar:
```powershell
docker exec auto-shots-postgres-1 psql -U clipia -d clipia -c "DELETE FROM users;"
python scripts/seed_admin.py
```

**Alembic 'column template_id does not exist':**
Era um bug em base zerada. Resolvido em commit `48b41f7` (Phase A).
Se aparecer em outro schema, aplicar `ALTER TABLE jobs ADD COLUMN template_id
VARCHAR(50) DEFAULT 'stock_narration'` antes de rodar `alembic upgrade`.

## 7. Ciclo de vida: Fase A -> B -> C

- **A (atual):** ressurreicao Windows, stack rodando, Gui e unico usuario admin.
- **B:** gpt-image-1 como media primaria; novos templates de novelinha.
- **C:** scheduler de canal, auto-upload YouTube.
- **D:** fork (continua creator ou reabre SaaS com showcase).

Cada fase tem spec em `docs/superpowers/specs/` e plano em `docs/superpowers/plans/`.
