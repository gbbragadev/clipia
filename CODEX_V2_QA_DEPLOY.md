# ClipIA v2 Fase 1 — QA Completo + Deploy para Produção

## Contexto

O ClipIA v2 Fase 1 (Narração Natural) foi implementado. Essa sessão adicionou:

### Stack (sem mudanças)
- **Backend**: Python 3.12, FastAPI, Celery, Redis, PostgreSQL (async SQLAlchemy + Alembic)
- **Frontend**: Next.js 16, React 19, Remotion 4, Tailwind CSS 4
- **Auth**: JWT (HS256, 24h), token `clipia_token` no localStorage
- **GPU**: RTX 3090 para Whisper (CUDA libs preloaded via ctypes)

### O que foi implementado (Fase 1)

#### Backend — Arquivos novos
- `app/services/voice_provider.py` — ABC VoiceProvider + factory get_voice_provider()
- `app/services/edge_provider.py` — EdgeTTSProvider (3 vozes pt-BR: Antonio, Francisca, Thalita)
- `app/services/elevenlabs_provider.py` — ElevenLabsProvider (TTS streaming, voice cloning, cache Redis 24h)
- `app/services/custom_audio_provider.py` — CustomAudioProvider (validate, normalize WAV via FFmpeg)

#### Backend — Arquivos modificados
- `app/config.py` — +ELEVENLABS_API_KEY, +KLING_ACCESS_KEY, +KLING_SECRET_KEY, +CREDIT_COST_EDGE/ELEVENLABS/CUSTOM_AUDIO/AI_VIDEO
- `app/db/models.py` — +VoiceClone model, +credit_cost/voice_provider/voice_config no Job, +voice_clones relationship no User
- `app/worker/tasks.py` — task_synthesize_audio agora lê voice_provider do Redis e dispatch por provider; refund usa job.credit_cost
- `app/api/routes.py` — 4 endpoints novos, /generate agora aceita voice_provider/voice_config e debita créditos variáveis
- `app/models.py` — GenerateRequest +voice_provider +voice_config, +VoiceCloneRequest, RegenerateTTSRequest +voice_provider (removeu validação hardcoded de voice_id)
- `alembic/versions/d697edf17fc9_*.py` — Migration: tabela voice_clones + campos no jobs (JÁ RODADA)

#### Endpoints novos
```
GET    /api/v1/voices                  — lista Edge + ElevenLabs + clones do user
POST   /api/v1/voices/clone            — voice cloning via ElevenLabs IVC (limite 5/user, rate 3/hora)
DELETE /api/v1/voices/{clone_id}       — deleta clone (DB + ElevenLabs API)
POST   /api/v1/jobs/{id}/upload-audio  — upload áudio custom (WAV/MP3/WebM, 5-180s, max 50MB) + Whisper transcription
```

#### Endpoints modificados
```
POST   /api/v1/generate               — agora aceita voice_provider ("edge"|"elevenlabs"|"custom") e voice_config (dict)
                                        Créditos variáveis: edge=1, elevenlabs=2, custom=1
POST   /api/v1/jobs/{id}/regenerate-tts — agora aceita voice_provider para ElevenLabs voices
```

#### Frontend — Arquivos novos
- `frontend/src/components/editor/AudioRecorder.tsx` — MediaRecorder + waveform canvas + gravar/pausar/parar/preview
- `frontend/src/lib/editor-api.ts` — +VoiceInfo type, +fetchVoices(), +uploadJobAudio()

#### Frontend — Arquivos modificados
- `frontend/src/components/editor/VoiceSelector.tsx` — Reescrito com 3 tabs (Grátis/Premium/Minha Voz), preview de áudio, rate/pitch condicional (só Edge)
- `frontend/src/components/dashboard/GenerateForm.tsx` — +seletor Edge/ElevenLabs, +crédito dinâmico (1 ou 2)
- `frontend/src/remotion/types.ts` — VoiceConfig +voiceProvider field

### Banco de dados
- `voice_clones`: id (UUID), user_id (FK→users), name, provider, external_voice_id, samples_count, created_at
- `jobs` ganhou: credit_cost (int, default 1), voice_provider (varchar, default "edge"), voice_config (JSONB, nullable)

### Configuração (.env)
```
ELEVENLABS_API_KEY=sk_96fe...  (já configurado)
KLING_ACCESS_KEY=AgYK...       (para Fase 3, não usado ainda)
KLING_SECRET_KEY=3aGJ...       (para Fase 3, não usado ainda)
CREDIT_COST_EDGE=1
CREDIT_COST_ELEVENLABS=2
CREDIT_COST_CUSTOM_AUDIO=1
CREDIT_COST_AI_VIDEO=5
```

---

## TAREFA 1: Testes Unitários — Voice Providers

### O que testar (tests/test_voice_providers.py)

Criar suite de testes para os 3 voice providers. Todos os testes devem rodar **sem dependências externas** (sem ElevenLabs API real, sem GPU, sem microfone).

#### EdgeTTSProvider
1. `test_edge_list_voices` — retorna 3 vozes pt-BR (Antonio, Francisca, Thalita)
2. `test_edge_estimate_cost` — retorna CREDIT_COST_EDGE (1)
3. `test_edge_synthesize` — mock edge_tts.Communicate, verifica que chama save() com parâmetros corretos
4. `test_edge_synthesize_with_duration_target` — verifica que chama _fit_to_duration quando duration_target > 0
5. `test_edge_provider_name` — provider_name == "edge"

#### ElevenLabsProvider
6. `test_elevenlabs_list_voices_cached` — com cache Redis populado, NÃO chama API
7. `test_elevenlabs_list_voices_uncached` — sem cache, chama API e popula cache
8. `test_elevenlabs_estimate_cost` — retorna CREDIT_COST_ELEVENLABS (2)
9. `test_elevenlabs_synthesize` — mock elevenlabs client, verifica text_to_speech.convert() chamado com voice_id e model_id corretos
10. `test_elevenlabs_synthesize_creates_wav` — verifica que PCM é convertido para WAV via ffmpeg (mock subprocess)
11. `test_elevenlabs_clone_voice` — mock voices.ivc.create, verifica retorno de voice_id e invalidação do cache
12. `test_elevenlabs_delete_voice` — mock voices.delete, verifica invalidação do cache
13. `test_elevenlabs_no_api_key_raises` — sem ELEVENLABS_API_KEY configurada, _get_client() levanta RuntimeError

#### CustomAudioProvider
14. `test_custom_estimate_cost` — retorna CREDIT_COST_CUSTOM_AUDIO (1)
15. `test_custom_list_voices` — retorna 1 voz (custom_upload)
16. `test_validate_audio_too_short` — áudio < 5s levanta ValueError
17. `test_validate_audio_too_long` — áudio > 180s levanta ValueError
18. `test_validate_audio_too_large` — arquivo > 50MB levanta ValueError
19. `test_normalize_audio` — mock subprocess.run, verifica args do ffmpeg (ar 24000, ac 1, pcm_s16le)

#### Factory
20. `test_get_voice_provider_edge` — retorna EdgeTTSProvider
21. `test_get_voice_provider_elevenlabs` — retorna ElevenLabsProvider
22. `test_get_voice_provider_custom` — retorna CustomAudioProvider
23. `test_get_voice_provider_unknown_raises` — provider inexistente levanta ValueError

### Como mockar

```python
# ElevenLabs client
from unittest.mock import patch, MagicMock
with patch('app.services.elevenlabs_provider._get_client') as mock_client:
    client = MagicMock()
    mock_client.return_value = client
    # configure client.text_to_speech.convert.return_value = iter([b"audio_bytes"])

# Redis para cache
import fakeredis
with patch('app.services.elevenlabs_provider.redis_lib.Redis.from_url') as mock_redis:
    mock_redis.return_value = fakeredis.FakeRedis(decode_responses=True)

# FFmpeg
with patch('subprocess.run') as mock_run:
    mock_run.return_value = MagicMock(returncode=0, stdout='{"format":{"duration":"10.5"}}')

# Edge TTS
with patch('app.services.edge_provider.edge_tts.Communicate') as mock_comm:
    instance = MagicMock()
    mock_comm.return_value = instance
    instance.save = AsyncMock()
```

### Verificação
```bash
cd ~/projects/auto-shorts
source .venv/bin/activate
pytest tests/test_voice_providers.py -v
```

---

## TAREFA 2: Testes de API — Novos Endpoints

### O que testar (tests/test_voice_endpoints.py)

Testar os 4 novos endpoints + modificações no /generate. Usar TestClient do FastAPI com banco de teste.

#### GET /api/v1/voices
1. `test_list_voices_authenticated` — retorna lista com pelo menos vozes Edge (sem ElevenLabs key = só Edge)
2. `test_list_voices_unauthenticated` — retorna 401
3. `test_list_voices_includes_user_clones` — com VoiceClone no banco, retorna na lista com is_clone=True

#### POST /api/v1/voices/clone
4. `test_clone_voice_success` — mock ElevenLabs, cria VoiceClone no banco, retorna voice_id
5. `test_clone_voice_no_files` — sem arquivos, retorna 400
6. `test_clone_voice_max_limit` — com 5 clones existentes, retorna 400 "Máximo de 5 vozes"
7. `test_clone_voice_unauthenticated` — retorna 401
8. `test_clone_voice_no_elevenlabs_key` — ELEVENLABS_API_KEY vazia, retorna 503

#### DELETE /api/v1/voices/{clone_id}
9. `test_delete_clone_success` — deleta do banco e chama ElevenLabs delete (mock)
10. `test_delete_clone_not_found` — clone_id inexistente, retorna 404
11. `test_delete_clone_other_user` — clone de outro user, retorna 404 (não 403, para não vazar info)

#### POST /api/v1/jobs/{id}/upload-audio
12. `test_upload_audio_success` — upload WAV válido, retorna audio_url e words (mock Whisper)
13. `test_upload_audio_too_large` — arquivo > 50MB, retorna 400
14. `test_upload_audio_no_file` — sem arquivo, retorna 400
15. `test_upload_audio_validates_format` — mock ffprobe retorna erro, retorna 400 "formato não reconhecido"
16. `test_upload_audio_unauthenticated` — retorna 401

#### POST /api/v1/generate (modificações)
17. `test_generate_with_edge_costs_1_credit` — voice_provider="edge", debita 1 crédito
18. `test_generate_with_elevenlabs_costs_2_credits` — voice_provider="elevenlabs", debita 2 créditos
19. `test_generate_with_elevenlabs_insufficient_credits` — user com 1 crédito + elevenlabs, retorna 402
20. `test_generate_passes_voice_config_to_redis` — verifica que voice_config é salvo no Redis hash do job
21. `test_generate_backwards_compatible` — sem voice_provider no request, default "edge", 1 crédito (não quebra clientes antigos)

#### POST /api/v1/jobs/{id}/regenerate-tts (modificações)
22. `test_regenerate_tts_with_edge` — voice_provider="edge", usa synthesize_narration_async
23. `test_regenerate_tts_with_elevenlabs` — voice_provider="elevenlabs", usa ElevenLabsProvider (mock)

### Fixtures necessárias

```python
@pytest.fixture
async def test_user(db):
    """User com email_verified=True e 10 créditos."""
    user = User(email="test@clipia.com", name="Test", password_hash=hash_password("test123"), credits=10, email_verified=True)
    db.add(user)
    await db.commit()
    return user

@pytest.fixture
def auth_headers(test_user):
    token = create_access_token(str(test_user.id))
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
async def test_clone(db, test_user):
    clone = VoiceClone(user_id=test_user.id, name="Minha voz", provider="elevenlabs", external_voice_id="el_123", samples_count=1)
    db.add(clone)
    await db.commit()
    return clone
```

### Verificação
```bash
pytest tests/test_voice_endpoints.py -v
```

---

## TAREFA 3: Testes de Worker — VoiceProvider no Pipeline

### O que testar (tests/test_worker_voice.py)

Testar que o worker Celery usa o provider correto baseado na configuração do job.

1. `test_synthesize_audio_edge_default` — sem voice_provider no Redis, usa Edge TTS (comportamento original)
2. `test_synthesize_audio_edge_explicit` — voice_provider="edge" no Redis, usa Edge TTS
3. `test_synthesize_audio_elevenlabs` — voice_provider="elevenlabs" + voice_config com voice_id no Redis, chama ElevenLabsProvider.synthesize (mock)
4. `test_synthesize_audio_custom` — voice_provider="custom" + voice_config.source_path no Redis, chama normalize_audio (mock)
5. `test_synthesize_audio_custom_missing_source` — custom sem source_path, levanta RuntimeError, job marcado como failed
6. `test_synthesize_audio_elevenlabs_no_voice_id` — elevenlabs sem voice_id, levanta RuntimeError
7. `test_refund_uses_credit_cost` — job com credit_cost=2, refund devolve 2 créditos (não 1)
8. `test_dispatch_pipeline_stores_voice_config` — dispatch_pipeline com voice_config, verifica que Redis hash tem voice_config e voice_provider
9. `test_dispatch_pipeline_backwards_compatible` — dispatch_pipeline sem voice args, voice_provider default "edge" no Redis

### Como mockar o worker

```python
# Redis para status do job
import fakeredis
_redis = fakeredis.FakeRedis(decode_responses=True)

# Patch no módulo tasks
with patch('app.worker.tasks._redis', _redis):
    # Setar voice config no Redis
    _redis.hset(f"job:{job_id}", mapping={
        "voice_provider": "elevenlabs",
        "voice_config": json.dumps({"voice_id": "el_abc123"}),
    })

# Mock synthesize
with patch('app.worker.tasks.synthesize_narration') as mock_edge:
    ...
with patch('app.services.elevenlabs_provider.ElevenLabsProvider.synthesize', new_callable=AsyncMock) as mock_el:
    ...
```

### Verificação
```bash
pytest tests/test_worker_voice.py -v
```

---

## TAREFA 4: Teste de Regressão — Pipeline Original Intacto

### O que testar (tests/test_regression_pipeline.py)

Garantir que NADA quebrou no fluxo original (Edge TTS, Pexels media, FFmpeg compose).

1. `test_generate_endpoint_still_works` — POST /generate com apenas topic/style/duration_target (sem voice_provider) funciona, retorna job_id
2. `test_edge_tts_still_works` — synthesize_narration() direta com "pt-BR-AntonioNeural" produz arquivo
3. `test_templates_endpoint_unchanged` — GET /templates retorna os 4 templates originais (stock, gameplay, character, story)
4. `test_job_status_format_unchanged` — campos do JobStatus não mudaram (job_id, status, progress, current_step, error, created_at, download_url)
5. `test_composition_endpoint_unchanged` — CompositionResponse tem os mesmos campos (+ template_id, layout_type)
6. `test_editor_save_still_works` — POST /edit com editor_state funciona
7. `test_regenerate_tts_edge_default` — POST /regenerate-tts sem voice_provider funciona como antes
8. `test_credits_debit_1_for_edge` — geração com template padrão debita 1 crédito (não 2)
9. `test_render_endpoint_unchanged` — POST /render funciona como antes
10. `test_job_list_format_unchanged` — GET /jobs retorna mesmos campos que antes

### Verificação
```bash
pytest tests/test_regression_pipeline.py -v
```

---

## TAREFA 5: Verificação TypeScript — Frontend sem erros

### O que verificar

```bash
cd ~/projects/auto-shorts/frontend
npx tsc --noEmit 2>&1
```

Se houver erros:
1. Identificar o arquivo e a linha
2. Corrigir o tipo ou import
3. NÃO alterar lógica de negócio — apenas correções de tipos

Verificar também que o build funciona:
```bash
npm run build 2>&1
```

### Coisas que podem dar erros de tipo
- `VoiceConfig.voiceProvider` — adicionado recentemente, pode ter referências sem o campo
- `GenerateParams.voice_provider` — campo novo, verificar que é optional
- `AudioRecorder.tsx` — component novo, verificar props tipadas

---

## TAREFA 6: Deploy para Produção (SÓ SE TODAS AS TAREFAS 1-5 PASSARAM)

### Pré-requisitos
- TODOS os testes das tarefas 1-4 passaram (0 failures)
- TypeScript compila sem erros (tarefa 5)
- Frontend builda com sucesso (tarefa 5)

### Sequência de deploy

#### 1. Verificação pré-deploy
```bash
cd ~/projects/auto-shorts
source .venv/bin/activate

# Rodar todos os testes
pytest tests/test_voice_providers.py tests/test_voice_endpoints.py tests/test_worker_voice.py tests/test_regression_pipeline.py -v --tb=short

# Contar falhas
pytest tests/ -q 2>&1 | tail -3
# Se houver QUALQUER falha: PARE AQUI. Não faça deploy.
```

#### 2. Build do frontend
```bash
cd ~/projects/auto-shorts/frontend
npm run build
# Se falhar: PARE AQUI.
```

#### 3. Commit das mudanças
```bash
cd ~/projects/auto-shorts
git add -A
git status  # revisar: NÃO commitar .env (deve estar no .gitignore)

# Verificar que .env NÃO está staged
git diff --cached --name-only | grep -E "^\.env$" && echo "PERIGO: .env staged, remova com git reset HEAD .env" && exit 1

git commit -m "feat(v2): phase 1 — voice providers (Edge/ElevenLabs/Custom), audio upload, variable credits

- VoiceProvider abstraction with factory pattern
- ElevenLabs integration (TTS, voice cloning, Redis cache)
- Custom audio upload + validation + FFmpeg normalization
- VoiceClone model + credit_cost/voice_provider/voice_config on Job
- 4 new endpoints: /voices, /voices/clone, /voices/{id}, /jobs/{id}/upload-audio
- Variable credit costs: edge=1, elevenlabs=2, custom=1
- VoiceSelector v2 with 3 tabs (Free/Premium/My Voice)
- AudioRecorder component (MediaRecorder + waveform)
- GenerateForm with voice provider selection
- Full backwards compatibility with existing pipeline"
```

#### 4. Restart dos serviços
```bash
# Backend (carrega novas rotas e config)
sudo systemctl restart clipia-backend

# Worker (carrega novo task_synthesize_audio com providers)
sudo systemctl restart clipia-worker

# Frontend (novo build com VoiceSelector v2)
sudo systemctl restart clipia-frontend

# Verificar que todos subiram
sleep 3
sudo systemctl status clipia-backend clipia-worker clipia-frontend --no-pager | grep -E "Active:|Main PID"
```

#### 5. Smoke test em produção
```bash
# Health check
curl -s https://api.clipia.com.br/health | python3 -c "import sys,json; d=json.load(sys.stdin); print('Health:', d.get('status'))"

# Voices endpoint (requer auth)
TOKEN=$(curl -s -X POST https://api.clipia.com.br/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"gui@clipia.com","password":"test123"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

# Listar vozes
curl -s https://api.clipia.com.br/api/v1/voices \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "
import sys, json
voices = json.load(sys.stdin)
print(f'Total voices: {len(voices)}')
providers = set(v.get('provider','?') for v in voices)
print(f'Providers: {providers}')
edge = [v for v in voices if v.get('provider')=='edge']
print(f'Edge voices: {len(edge)}')
"

# Templates (deve retornar 4 originais)
curl -s https://api.clipia.com.br/api/v1/templates \
  -H "Authorization: Bearer $TOKEN" \
  | python3 -c "import sys,json; t=json.load(sys.stdin); print(f'Templates: {len(t)}')"

# Frontend carrega
curl -sI https://clipia.com.br | head -3
```

#### 6. Resultado esperado do smoke test
```
Health: ok
Total voices: 3+  (Edge voices mínimo, ElevenLabs se configurado)
Providers: {'edge'} ou {'edge', 'elevenlabs'}
Edge voices: 3
Templates: 4
HTTP/2 200
```

Se QUALQUER passo falhar, rollback:
```bash
# Rollback git
cd ~/projects/auto-shorts
git log --oneline -3  # identificar o commit anterior
git revert HEAD --no-edit  # reverte o commit, mantém no histórico

# Restart services com código anterior
sudo systemctl restart clipia-backend clipia-worker clipia-frontend
```

### IMPORTANTE
- **NÃO faça deploy se algum teste falhar**
- **NÃO commite o .env** (tem API keys reais)
- **NÃO modifique o .env em produção** (já tem as keys configuradas)
- **Se o smoke test falhar**: revert o commit, restart services, reportar o problema
- **Celery worker PRECISA de restart** após mudar assinaturas de tasks
