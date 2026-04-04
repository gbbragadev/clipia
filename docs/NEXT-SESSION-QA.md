# ClipIA — Sessão de QA, Refinamento e Validação de Qualidade

## Gatilho para a próxima sessão

> **Cole isso no início da próxima sessão:**
> "Leia o arquivo docs/NEXT-SESSION-QA.md e execute o plano de QA descrito. O objetivo é que o ClipIA gere vídeos com qualidade real para um usuário final — não algo quebrado ou amador."

---

## Estado Atual (2026-04-04)

### O que funciona
- Pipeline end-to-end: roteiro → TTS → whisper → mídia → compositor → vídeo final
- Auth JWT completo (register, login, créditos)
- PostgreSQL com users, jobs, waitlist
- FFmpeg + NVENC para composição (~10s vs 158s anterior)
- Legendas ASS (geradas mas precisam validação visual)
- Frontend com login/registro, landing page com VideoShowcase

### O que está QUEBRADO agora
1. **TTS lê SSML tags como texto** — `<break time="400ms"/>` aparece literalmente na narração
   - **Causa**: `edge_tts.Communicate()` não suporta SSML raw no parâmetro `text`
   - **Fix**: Remover os SSML breaks. Edge TTS já faz pausas naturais em pontuação. Alternativa: usar `edge_tts.Communicate` com o parâmetro de texto limpo, sem SSML
   - **Arquivo**: `app/services/tts.py` — função `_add_prosody()` está injetando tags

2. **Conteúdo cortado** — vídeo pode ter cenas faltando ou narração truncada
   - Investigar se `scenes` do script batem com `media_paths` 
   - Verificar se duração do áudio bate com soma das scene durations

3. **Roteiro pode estar desconexo** — validar se o novo prompt produz arco narrativo coerente

4. **Legendas** — validar visualmente se:
   - Estão posicionadas corretamente (não cortadas)
   - Font size está legível
   - Timing sincronizado com áudio
   - Estilo TikTok (background semi-transparente)

5. **Tamanho do arquivo** — 38.8MB para 34s é excessivo. Precisa ajustar bitrate

---

## Plano de QA (executar nesta ordem)

### Fase 1: Fix Imediato do TTS
- Remover `_add_prosody()` do tts.py — Edge TTS não aceita SSML inline
- Edge TTS já pausa naturalmente em `.`, `!`, `?`
- Testar TTS isolado: gerar audio e ouvir se ficou natural

### Fase 2: Gerar Vídeo de Teste
- Gerar 3 vídeos com temas diferentes:
  1. `"5 curiosidades sobre o oceano"` (curiosity, 30s)
  2. `"como fazer café perfeito"` (educational, 35s)
  3. `"fatos surpreendentes sobre gatos"` (curiosity, 25s)
- Para CADA vídeo, validar:

### Fase 3: Checklist de Qualidade por Vídeo

**Roteiro:**
- [ ] Tem gancho nos primeiros 3 segundos?
- [ ] Arco narrativo: abertura → desenvolvimento → conclusão?
- [ ] Frases curtas e conversacionais?
- [ ] Word count compatível com duração alvo?
- [ ] Scene duration_hints somam ≈ duração alvo?

**Narração (TTS):**
- [ ] Sem artefatos (sem SSML lido, sem glitches)?
- [ ] Velocidade confortável para entender?
- [ ] Pausas naturais entre frases?
- [ ] Duração do áudio ≈ duração alvo (±5s)?

**Legendas:**
- [ ] Visíveis no frame (não cortadas)?
- [ ] Posicionadas na parte inferior sem obstruir conteúdo?
- [ ] Sincronizadas com a fala?
- [ ] Font legível em tela de celular?
- [ ] Estilo moderno (não datado)?

**Mídia:**
- [ ] Vídeos são portrait (9:16)?
- [ ] Relevantes ao tema da narração?
- [ ] Sem letterboxing ou distorção?
- [ ] Transições suaves entre cenas?

**Composição:**
- [ ] Áudio sincronizado com vídeo?
- [ ] Sem frames pretos ou freezes?
- [ ] Resolução 1080x1920?
- [ ] Tamanho de arquivo razoável (<15MB para 30s)?

**Tempo:**
- [ ] Geração total < 60s?
- [ ] Compositing < 15s?

### Fase 4: Refinamento
Para cada item que FALHAR no checklist:
1. Identificar root cause
2. Implementar fix
3. Regenerar vídeo
4. Revalidar

### Fase 5: Comparação A/B
- Gerar o MESMO tema ("curiosidades sobre gatos") que falhou antes
- Comparar lado-a-lado com o vídeo anterior
- O novo deve ser claramente melhor

---

## Arquivos Chave para Referência

| Arquivo | O que faz | Provável fix |
|---------|-----------|--------------|
| `app/services/tts.py` | TTS com Edge TTS | REMOVER `_add_prosody()`, testar sem SSML |
| `app/services/scriptwriter.py` | Prompt Claude para roteiro | Validar output, ajustar se roteiros fracos |
| `app/services/subtitles.py` | Gera arquivo .ass | Ajustar posição/font se legendas ruins |
| `app/services/compositor.py` | FFmpeg pipeline | Ajustar bitrate, verificar concat |
| `app/services/media.py` | Busca Pexels | Verificar se portrait, qualidade |
| `app/worker/tasks.py` | Orquestra pipeline | Logs entre steps |

## Skills Recomendadas

1. **`/investigate`** — Para debugar cada problema encontrado no QA
2. **`/qa`** — Para testar o fluxo end-to-end via browser (gstack)
3. **`/gstack`** — Para abrir o site, testar a geração visual, verificar legendas no vídeo
4. **`/health`** — Para verificar que containers, worker e API estão saudáveis

## Comandos Úteis

```bash
# Verificar estado dos containers
docker compose ps

# Reiniciar worker (PRECISA do LD_LIBRARY_PATH para Whisper/CUDA)
pkill -9 -f celery; sleep 2
LD_LIBRARY_PATH="/usr/local/lib/ollama/cuda_v12" nohup .venv/bin/celery -A app.worker.celery_app worker -l info --concurrency=1 > /tmp/clipia-worker.log 2>&1 &

# Dar créditos para testar
docker compose exec postgres psql -U clipia -c "UPDATE users SET credits = 20 WHERE email = 'gui@clipia.com';"

# Gerar vídeo via API
TOKEN=$(curl -s -X POST http://localhost:8005/api/v1/auth/login -H "Content-Type: application/json" -d '{"email":"gui@clipia.com","password":"test123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -s -X POST http://localhost:8005/api/v1/generate -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d '{"topic":"TEMA","style":"curiosity","duration_target":30}'

# Logs do worker
tail -f /tmp/clipia-worker.log

# Verificar vídeo gerado
ffprobe -v quiet -print_format json -show_format storage/output/JOB_ID.mp4

# URLs
# Frontend: https://autoshorts.gbbragadev.com
# API: https://api-autoshorts.gbbragadev.com
# Swagger: https://api-autoshorts.gbbragadev.com/docs

# Auth test user: gui@clipia.com / test123
# PostgreSQL: localhost:5435, user=clipia, pass=clipia_dev, db=clipia
# Redis: localhost:6382
```
