# ClipIA Editor — QA e Ajustes (Proxima Sessao)

## Gatilho

> **Cole isso no inicio da proxima sessao:**
> "Leia o arquivo docs/NEXT-SESSION-QA-EDITOR.md e execute o plano de QA do editor. O objetivo e que todas as funcionalidades do editor funcionem corretamente para um usuario real."

---

## Estado Atual (2026-04-04)

### O que foi construido
- Editor com Remotion Player (video preview 9:16)
- Layout CSS Grid 3 zonas (header/workspace/timeline)
- 5 abas: Cenas, Voz, Legendas, Elementos, IA
- SceneGrid com thumbnails + edicao inline de texto
- VoiceSelector conectado ao context (3 vozes pt-BR + rate/pitch)
- SubtitleEditor com CaptionStylePicker (3 presets: Minimal, TikTok, Impact)
- OverlayPicker (QuestionBox, FollowCTA, EndScreen, ProgressBar)
- AIAssistant com chat Claude (4 quick prompts + input livre)
- ExportPanel com download + captions sociais (YouTube/TikTok/Instagram)
- EditorTimeline full-width com scene blocks + playhead + transport controls
- Keyboard shortcuts (Space, arrows, J/L, 1-9, Tab, Ctrl+Z)
- Transitions entre cenas (@remotion/transitions: fade/slide/wipe)
- Undo/redo history stack (50 entries)

### Bugs Conhecidos (TESTAR E CORRIGIR)

#### 1. **401 Unauthorized em todos os POST endpoints** (CRITICO)
Os endpoints `/regenerate-tts`, `/ai-suggest`, `/edit` retornam 401.
**Causa**: O token JWT esta salvo no localStorage como `token`, mas os componentes usam `localStorage.getItem('token')` diretamente em vez de usar o AuthContext.
**Investigar**: 
- Como o AuthContext salva o token (`frontend/src/contexts/AuthContext.tsx`)
- Se a key e `token` ou outra coisa
- Se o token esta sendo passado no header `Authorization: Bearer {token}`
**Fix provavel**: Verificar a key do localStorage no AuthContext e alinhar com os componentes do editor.

#### 2. **Timeline nao acompanha o video durante playback**
O polling de 100ms foi adicionado ao EditorContext, mas precisa verificar se:
- O `playerRef.current` esta acessivel (o Player e carregado com `dynamic import ssr: false`)
- O `.getCurrentFrame()` e `.isPlaying()` funcionam no Remotion 4
- O playhead (linha cyan) se move durante a reproducao
**Testar**: Dar play no video e observar se a linha do playhead se move.

#### 3. **Click na timeline pode nao funcionar**
O `seekToFrame` chama `playerRef.current?.seekTo(frame)` mas:
- O Player pode precisar de um `.pause()` antes do `.seekTo()` para funcionar
- O `clickToPlay` prop pode interferir
**Testar**: Clicar em diferentes pontos da timeline e ver se o player pula.

#### 4. **Narration regeneration** (erro 401, alem disso precisa testar):
- Se Edge TTS gera audio com voz diferente (Francisca, Thalita)
- Se Whisper roda no processo da API (precisa do LD_LIBRARY_PATH para CUDA)
- Se o audio novo carrega no Remotion Player (cache bust com timestamp)

#### 5. **AI Assistant** (erro 401, alem disso testar):
- Se Claude retorna JSON valido
- Se o botao "Aplicar" atualiza a cena no editor
- Se o preview do Remotion reflete a mudanca

#### 6. **Caption styles podem nao renderizar no Player**
Os componentes TikTokCaptions e ImpactCaptions foram criados mas precisam de teste visual:
- Selecionar preset "TikTok" → legendas devem mudar para pill + karaoke amarelo
- Selecionar "Impact" → legendas bold uppercase com stroke 3D
**Se nao renderizar**: Verificar se o SubtitleOverlay esta importando os componentes corretamente.

#### 7. **Overlays podem nao aparecer**
Os overlays (QuestionBox, etc.) precisam ser adicionados manualmente na aba Elementos.
**Testar**: Adicionar um QuestionBox → deve aparecer no Player nos primeiros 5s.
**Se nao aparecer**: Verificar se `composition.overlays` esta sendo passado ao ShortVideoComposition.

#### 8. **Transitions podem nao funcionar**
O TransitionSeries foi adicionado mas precisa verificar:
- Se `@remotion/transitions` exporta `fade`, `slide`, `wipe` corretamente
- Se a composicao renderiza sem erro com transitions ativadas

#### 9. **Export pode falhar**
O endpoint `/render` atual so copia o final.mp4 existente — nao re-renderiza com edicoes.
**Para o futuro**: Implementar re-render real via Celery com os parametros editados.

---

## Plano de QA (executar nesta ordem)

### Fase 1: Fix do Auth (401)
1. Ler `frontend/src/contexts/AuthContext.tsx` para ver como token e salvo
2. Verificar se VoiceSelector, AIAssistant e auto-save usam a mesma key
3. Corrigir — provavelmente mudar para `localStorage.getItem('access_token')` ou usar o AuthContext

### Fase 2: Testar Timeline Sync
1. Abrir editor, dar play no video
2. Verificar se playhead (linha cyan) se move
3. Se nao move: investigar se polling funciona, se playerRef esta populado
4. Clicar em pontos da timeline — player deve pular
5. Clicar em thumbnails de cena — player deve pular para inicio da cena

### Fase 3: Testar Narration Regen (apos fix do 401)
1. Mudar voz para Francisca
2. Clicar "Regerar narracao"
3. Verificar se audio novo carrega
4. Verificar se timestamps (legendas) atualizam

### Fase 4: Testar AI Assistant (apos fix do 401)
1. Clicar quick prompt "Melhorar gancho"
2. Verificar se Claude responde com sugestoes
3. Clicar "Aplicar" numa sugestao
4. Verificar se texto da cena atualiza no SceneGrid
5. Verificar se preview do Player reflete a mudanca

### Fase 5: Testar Caption Styles
1. Ir na aba Legendas
2. Selecionar preset "TikTok" → ver mudanca no Player
3. Selecionar preset "Impact" → ver mudanca no Player
4. Mudar cor do accent → ver reflexo no Player
5. Mudar tamanho da fonte → ver reflexo no Player

### Fase 6: Testar Overlays
1. Ir na aba Elementos
2. Adicionar "Caixa de Pergunta" → deve aparecer no Player (primeiros 5s)
3. Adicionar "Seguir CTA" → deve aparecer no meio do video
4. Adicionar "Tela Final" → deve aparecer nos ultimos 5s
5. Remover overlay → deve sumir do Player

### Fase 7: Testar Transitions
1. Selecionar uma cena no SceneGrid
2. Mudar transicao para "Fade"
3. Ver se transicao aparece entre cenas no Player

### Fase 8: Testar Export
1. Clicar "Exportar Video"
2. Selecionar qualidade
3. Clicar "Iniciar Export"
4. Verificar se download funciona
5. Verificar se captions sociais sao geradas
6. Testar "Copiar" nas captions

### Fase 9: Melhorias Visuais
Apos tudo funcional, avaliar:
- Player esta grande o suficiente?
- UI esta intuitiva?
- Cores/contraste estao adequados?
- Elementos de social media estao com visual profissional?

---

## Arquivos Chave

| Arquivo | Funcao |
|---------|--------|
| `frontend/src/contexts/AuthContext.tsx` | Como o token e salvo (investigar key) |
| `frontend/src/contexts/EditorContext.tsx` | Estado central, playerRef, seek, undo |
| `frontend/src/components/editor/EditorLayout.tsx` | Layout principal, tabs, export |
| `frontend/src/components/editor/VideoPlayer.tsx` | Remotion Player wrapper |
| `frontend/src/components/editor/EditorTimeline.tsx` | Timeline interativa |
| `frontend/src/components/editor/VoiceSelector.tsx` | Seletor de voz + regen |
| `frontend/src/components/editor/AIAssistant.tsx` | Chat com Claude |
| `frontend/src/components/editor/SubtitleEditor.tsx` | Editor de legendas |
| `frontend/src/components/editor/CaptionStylePicker.tsx` | Presets de caption |
| `frontend/src/components/editor/OverlayPicker.tsx` | Adicionar overlays |
| `frontend/src/components/editor/ExportPanel.tsx` | Modal de export |
| `frontend/src/remotion/compositions/ShortVideoComposition.tsx` | Composicao video |
| `frontend/src/remotion/compositions/SubtitleOverlay.tsx` | Routing de presets |
| `frontend/src/components/editor/overlays/*.tsx` | Componentes de overlay |
| `app/api/routes.py` | Backend endpoints |
| `app/services/tts.py` | TTS com parametros de voz |

## Comandos Uteis

```bash
# Frontend dev
cd ~/projects/auto-shorts/frontend && npm run dev -- -p 3003

# Backend (ja rodando com --reload)
# Verificar: curl http://localhost:8005/health

# Logs do backend
tail -f /tmp/clipia-backend.log

# TypeScript check
cd ~/projects/auto-shorts/frontend && npx tsc --noEmit

# Build
cd ~/projects/auto-shorts/frontend && npx next build

# Testar endpoint com auth
TOKEN=$(curl -s -X POST http://localhost:8005/api/v1/auth/login -H "Content-Type: application/json" -d '{"email":"gui@clipia.com","password":"test123"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
curl -s -X POST http://localhost:8005/api/v1/jobs/JOB_ID/regenerate-tts -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d '{"voice_id":"pt-BR-FranciscaNeural"}'

# URL do editor
# https://autoshorts.gbbragadev.com/editor/0c0ad29d-731c-455a-9d78-d585e0846feb
```
