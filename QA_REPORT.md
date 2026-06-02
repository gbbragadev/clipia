# QA Report

Data: 2026-04-26

## Resumo

Total: 9
Passou: 8
Falhou: 1
Bloqueado: 0

| Fluxo | Resultado | Evidencia |
| --- | --- | --- |
| Testes backend (`.venv312\\Scripts\\python.exe -m pytest -q`) | PASS | 231 passed, 3 warnings de teardown `aiosqlite` |
| Build frontend (`cmd /c npm run build`) | PASS | Next.js 16.2.2 build OK |
| Typecheck frontend (`cmd /c npx tsc --noEmit`) | PASS | Sem erros |
| API backend local | PASS | `GET /health` 200 |
| API templates via frontend proxy | PASS | `GET /api/v1/templates` retornou 5 templates |
| Login PinchTab em `http://localhost:3003/auth/login` | PASS | `evidence\\qa-pinchtab-dashboard-2026-04-26.jpg` |
| Dashboard PinchTab | PASS | `evidence\\qa-pinchtab-dashboard-app-2026-04-26.jpg` |
| Geracao completa Stock + Edge TTS | PASS | `evidence\\qa-pinchtab-generation-complete-dashboard-2026-04-26.jpg` |
| Login em host `127.0.0.1:3003` | FAIL | `evidence\\qa-login-after-submit-clean-profile-2026-04-26.jpg` |

## Fluxo Critico Validado

TESTE: Login + dashboard + geracao + editor
RESULTADO: PASS
PASSOS:
  [ok] 1. Abrir `http://localhost:3003/auth/login` via PinchTab.
  [ok] 2. Preencher email/senha usando refs (`e0`, `e2`) e clicar `Entrar`.
  [ok] 3. Confirmar landing autenticada com link `Dashboard`.
  [ok] 4. Abrir dashboard e confirmar templates, creditos e lista de videos.
  [ok] 5. Preencher tema e clicar `Gerar Video`.
  [ok] 6. Worker executou roteiro, TTS, transcricao Groq, Pexels, composicao FFmpeg e finalize.
  [ok] 7. Dashboard atualizou para 13 videos, novo job `PRONTO`, creditos 999997 -> 999996.
  [ok] 8. Editor abriu via URL do job e carregou 5 cenas/timeline/player.
EVIDENCIA:
  - `evidence\\qa-pinchtab-generate-clicked-2026-04-26.jpg`
  - `evidence\\qa-pinchtab-generation-complete-dashboard-2026-04-26.jpg`
  - `evidence\\qa-pinchtab-editor-direct-2026-04-26.jpg`
  - `storage\\output\\50384a34-ce7d-4b96-af88-32d46b9e2a48.mp4`

## Artefato Gerado

- Job: `50384a34-ce7d-4b96-af88-32d46b9e2a48`
- Arquivo: `storage\\output\\50384a34-ce7d-4b96-af88-32d46b9e2a48.mp4`
- Codec/dimensoes: H.264, 1080x1920
- Duracao: 45.0s
- Tamanho: 16.2 MB

## Bugs

### BUG-001: Host `127.0.0.1:3003` quebra hidratacao do Next dev

Severidade: MEDIO

Reproducao:
1. Abrir `http://127.0.0.1:3003/auth/login`.
2. Preencher email/senha.
3. Clicar `Entrar`.

Resultado observado: o form executa submit nativo para `/auth/login?`, limpa os campos e nao chama `/api/v1/auth/login`. Console Playwright mostrou falhas HMR `ERR_INVALID_HTTP_RESPONSE`.

Esperado: comportamento igual a `http://localhost:3003`, que autentica corretamente.

Observacao: em `localhost` o login funciona. Para QA local, usar `localhost`; para robustez, corrigir suporte a `127.0.0.1` no dev server/origins/HMR.

### BUG-002: Preco exibido no card de template nao bate com custo real

Severidade: MEDIO

Reproducao:
1. Abrir dashboard.
2. Observar template `Narracao + Stock`.
3. Comparar card do template com bloco `Voz` e debito real.

Resultado observado: card mostra `2 creditos`, mas voz Edge mostra `1 credito` e a geracao debitou 1 credito.

Esperado: card deveria mostrar o custo do provedor selecionado ou uma faixa clara por voz/template.

## Observacoes

- Playwright confirmou que o botao `Editar` do card navega corretamente para `/editor/{jobId}`; uma tentativa via PinchTab nao navegou, mas nao ficou confirmado como bug do produto.
- O ambiente local tem 11 jobs antigos em erro. A geracao nova desta sessao passou, mas o historico sugere que resiliencia operacional ainda precisa de acompanhamento.
- O fluxo validado usa template Stock + Edge TTS. O template `Drama Historico` com imagem IA/ElevenLabs nao foi executado neste ciclo.

## Recomendacoes

- Corrigir a discrepancia de creditos antes de cobrar usuarios reais.
- Adicionar teste e2e para login, dashboard, geracao mockada e abertura do editor.
- Validar `Drama Historico` e voz premium com ao menos 3 videos reais antes de qualquer oferta paga.
- Separar `dev host` suportado oficialmente: `localhost` ou `127.0.0.1`, mas nao deixar os dois com comportamento diferente.
- Adicionar monitoramento de taxa de sucesso por etapa: roteiro, TTS, transcricao, media, composicao, finalize.
