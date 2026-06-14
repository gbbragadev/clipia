# QA_PROMPT — Iteração de QA do ClipIA (ralph loop)

> **Modelo recomendado: Sonnet** (QA repetitivo de 50 iterações — Sonnet é econômico e suficiente).
> O ralph herda o modelo da sessão: troque com `/model sonnet` ANTES de iniciar o `/ralph-loop`.

Você é um QA automatizado do ClipIA. **Execute UMA única iteração** das etapas abaixo, grave o
resultado em `qa/ralph/QA_LEDGER.md` e `qa/ralph/QA_BUGS.md`, e então **encerre** (o ralph re-injeta
este prompt de novo). Só emita o promise quando o critério de **QA GREEN** for atingido (etapa 7).

Trabalhe sempre a partir de `C:\Dev\clipia`. Responda em pt-BR. Seja conciso: o valor está nos arquivos
de estado, não em texto longo no chat.

---

## 0. Setup do gstack browse (rode sempre, no início da iteração)

```bash
_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
B="$_ROOT/.claude/skills/gstack/browse/dist/browse"
[ -x "$B" ] || B=~/.claude/skills/gstack/browse/dist/browse
$B status >/dev/null 2>&1 || $B goto about:blank >/dev/null 2>&1
TS=$(date +%Y%m%d-%H%M%S)
EV="$_ROOT/qa/ralph/evidence"; mkdir -p "$EV"   # evidence/ é git-ignored; criar se não existir
```

Use `$B <comando>` para tudo no navegador. Evidência sempre em `$EV/<ID>-run<N>-$TS.png`.

---

## 1. PREFLIGHT (pré-condições — se falhar, registre BLOCKED e ENCERRE sem promise)

```bash
# IMPORTANTE: no preflight use 127.0.0.1 + curl -4. `localhost` resolve para IPv6 (::1) e PENDURA (000) no
# Next dev — isso é gotcha de curl, NÃO o servidor caído. (No BROWSER continue usando localhost — BUG-001.)
curl -4 -s -o /dev/null -w "%{http_code}" --max-time 8 http://127.0.0.1:8005/health   # espera 200
curl -4 -s -o /dev/null -w "%{http_code}" --max-time 8 http://127.0.0.1:3003          # espera 200
```

- Se der `000`/timeout, **confirme via browser** antes de declarar BLOCKED: `$B goto http://localhost:3003/`
  + `$B js "document.title"`. Se o browser renderiza, a stack está no ar (era só o curl IPv6) — siga normalmente.
- Se realmente caiu (browser também falha): anote no `QA_LEDGER.md` (seção "Eventos") uma linha
  `BLOCKED preflight <timestamp>: frontend=<code> backend=<code>` e **encerre a iteração** (NÃO emita promise).
  O Gui sobe a stack com `.\scripts\start-all.ps1`. Não tente subir você mesmo.

---

## 2. AUTH (garantir sessão autenticada — só re-loga se a sessão caiu)

A sessão do gstack persiste entre iterações. Verifique antes de re-logar:

```bash
$B goto http://localhost:3003/dashboard
$B js "localStorage.getItem('clipia_token') ? 'LOGGED' : 'ANON'"
```

Se `ANON` (ou redirecionou para /auth/login), faça login pela UI (**use `localhost`, NUNCA `127.0.0.1`** — BUG-001):

```bash
PWD=$(grep '^password:' "$_ROOT/.admin-credentials.local" | awk '{print $2}')
$B goto http://localhost:3003/auth/login
$B snapshot -i                      # descubra os refs dos campos email/senha e do botão Entrar
$B fill '#email' gbbraga.dev@gmail.com
$B fill '#password' "$PWD"
$B click 'button[type="submit"]'
$B wait --networkidle
$B js "localStorage.getItem('clipia_token') ? 'LOGGED' : 'ANON'"   # confirme LOGGED
```

Se continuar `ANON` após login → bug F02 `confirmed`, registre e siga (não trave o loop).

---

## 3. ESCOLHER O FLUXO DESTA ITERAÇÃO

Leia `qa/ralph/QA_LEDGER.md`. Escolha o fluxo `F*` com **menor `run_count`** (empate → ordem do catálogo).
Releia também `ciclo_atual` e os flags `gerou_no_ciclo` / `smoke_prod_no_ciclo`.

- Se o escolhido for **F06 (geração)** e `gerou_no_ciclo = sim`, pule para o próximo de menor run_count.
- Quando **todos** os `F*` tiverem `run_count` igual ao início de um novo ciclo, incremente `ciclo_atual`,
  zere `gerou_no_ciclo` e `smoke_prod_no_ciclo`, e rode o **SMOKE PROD** (etapa 6) nesta iteração.

---

## 4. EXECUTAR o fluxo (catálogo com seletores concretos)

Padrão de cada fluxo: `goto` → `snapshot -i` → interagir por refs `@e` → `snapshot -D` (confirmar mudança)
→ `$B console --errors` (capturar JS errors) → `$B network` (requests falhos) → `is visible` nas asserções
→ `$B screenshot "$EV/<ID>-run<N>-$TS.png"`. **200 não é prova**: o veredito vem de console limpo + asserção visual.

**Console: ATENÇÃO — a porta 3003 é `next start` (build de PRODUÇÃO), não dev.** Então `500`/`404` em
`/_next/static/chunks/*` **não** é "ruído de turbopack dev" — pode ser **build inconsistente** (o HTML referencia
um chunk que não foi emitido no `.next/static/chunks/`). Regra de triagem ao ver `500`/`404`/`ChunkLoadError` em chunk:
1. Faça `$B restart` + `goto <url>?nocache=$(date +%s)` (HTML fresco). Se o erro **sumiu** → era cache stale pós-rebuild → ignore.
2. Se **persistir**: pegue o HTML real (`curl -4 -s http://127.0.0.1:3003<rota>`), extraia os chunks referenciados e teste cada um:
   ```bash
   curl -4 -s http://127.0.0.1:3003<rota> | grep -oE '/_next/static/chunks/[^"]+\.(js|css)' | sort -u | \
     while read ch; do echo "$(curl -4 -s -o /dev/null -w '%{http_code}' http://127.0.0.1:3003$ch) $ch"; done
   ```
   Se algum chunk referenciado dá `500`/`404` **e não existe** em `frontend/.next/static/chunks/` → **BUG `alta` de build**
   (quebra hidratação → login/render falham). Confirme em prod (`curl https://clipia.com.br<ch>`). Registre e **não ignore**.
Outros erros que sempre contam: rota de **app/API** (`/api/v1/...` 4xx/5xx) e runtime React ("Minified React error #310",
"Hydration failed"). **Em produção (P*) o console deve estar 100% limpo.**
Sinal indireto de hidratação quebrada: `is visible "main"`/`"h1"` = false e login não grava `clipia_token` (fica ANON).

**F01 — Landing `/`** (`http://localhost:3003/`)
- Hero visível, seção showcase, CTA. `links` não-quebrados. `console --errors` vazio.
- Responsivo: `$B responsive "$EV/F01-resp-$TS"` (mobile 375 / tablet / desktop). PASS se hero aparece nos 3.

**F02 — Login `/auth/login`**
- Caminho infeliz: `fill #email a@a.com`, `fill #password xxx`, submit → asserir caixa de erro `.bg-red-500\/10` visível.
- Caminho feliz já coberto na etapa 2 (token presente). PASS = erro aparece no inválido E token presente no válido.

**F03 — Register `/auth/register`** (só validação client — **NÃO** submeter caminho-feliz real)
- `fill #password "abc"` → submit → erro "no minimo 8 caracteres".
- `fill #password "abcdefgh"` → erro "1 letra maiuscula".
- `fill #password "Abcdefgh"` → erro "1 numero". PASS = as 3 mensagens aparecem.

**F04 — Verify/Forgot/Reset** (páginas carregam + validação; **NÃO** completar OTP real)
- `/auth/verify?email=qa@test.com`, `/auth/forgot-password`, `/auth/reset-password?email=qa@test.com` carregam sem erro de console.
- Em verify: submeter código incompleto (<6 dígitos) → asserir mensagem de erro. PASS = páginas ok + erro de validação.

**F05 — Dashboard `/dashboard`**
- Saudação `h1` com "Olá", badge de créditos visível, grid de vídeos OU empty state ("Nenhum vídeo ainda").
- `console --errors` vazio. PASS = saudação + créditos + (grid ou empty) presentes.

**F06 — GenerateForm (1x por ciclo — geração real barata)**
- Primeiro a validação (sempre): topic curto deixa o botão "Gerar Vídeo" disabled.
  `fill` o input de tema com `"curto"` → `is disabled` no botão Gerar = PASS da validação.
- Se `gerou_no_ciclo = não`: gerar de verdade. Tema `"[QA] 3 curiosidades sobre o oceano profundo"`,
  template Stock/Narração, **voz Edge TTS** (barato). Clicar "Gerar Vídeo". Pollar status:
  ```bash
  # repetir a cada ~10s, máx ~240s, lendo o status do job mais novo
  $B js "document.body.textContent" | grep -iEo 'PRONTO|ERRO|gerando|finalizando' | head -1
  ```
  Quando concluir, capturar o `jobId` do card mais novo (via `$B links` ou `$B js`) e gravar em
  `QA_LEDGER.md` como `ultimo_job=<id>`. Setar `gerou_no_ciclo=sim`. PASS = job chega a PRONTO; se ERRO → bug F06.

**F07 — Editor `/editor/[jobId]`** (usa `ultimo_job` do ledger; se vazio, pegar qualquer job PRONTO do dashboard)
- `goto http://localhost:3003/editor/<jobId>`. Esperar `.editor-player-container` visível.
- Clicar nas 5 abas `button.editor-tab` (Cenas/Voz/Legendas/Elementos/IA) e confirmar `button.editor-tab--active` muda
  e `.editor-panel-content` re-renderiza (`snapshot -D`). Selecionar uma cena no SceneGrid. PASS = 5 abas trocam + cena selecionável + console limpo.

**F08 — Export (modal)** (no editor já aberto)
- Clicar `button.editor-header__export` → modal aparece. Conferir captions por plataforma (YT/TikTok/IG) e copy-to-clipboard.
- **NÃO** clicar render real. PASS = modal abre + captions presentes. Fechar o modal ao fim.

**F09 — Settings `/dashboard/settings`**
- Atualizar nome (campo `#name`) e salvar → toast sucesso. Conferir validação da troca de senha (campos placeholder "Senha atual"/"Nova senha").
- **NUNCA** clicar "Excluir minha conta" nem preencher o campo de confirmação de exclusão. PASS = nome salva + validação de senha responde.

**F10 — Credits `/dashboard/credits`** — carrega, mostra saldo/histórico, console limpo. PASS = página renderiza sem erro.

**F11 — Logout** — abrir o dropdown do usuário (canto sup. direito), clicar Sair → redireciona p/ `/auth/login` ou landing anon.
- `$B js "localStorage.getItem('clipia_token')"` deve ser `null`. **Depois re-logar na próxima iteração (etapa 2).** PASS = token limpo + redirect.

**F12 — Estáticas/Blog/Landing pages** — `/blog`, `/blog/<slug>`, `/privacidade`, `/termos`, **`/exemplos`** e as
landing por nicho **`/criar/<nicho>`** (curiosidades, religioso, motivacional, +4) renderizam, console limpo. PASS = todas carregam.

**F13 — Admin `/dashboard/admin`** — carrega para o seed admin sem erro de permissão/console. PASS = painel renderiza.

### Fluxos de SEGURANÇA (S*) — review de segurança do site

Baratos (curl + `$B js`). Rodam no rodízio junto dos `F*`. Para prod, a versão read-only roda no smoke (etapa 6).

**S01 — Rotas protegidas não vazam dados (deslogado)**
```bash
$B js "localStorage.clear(); sessionStorage.clear(); 'cleared'"
```
Para cada rota protegida (`/dashboard`, `/dashboard/settings`, `/dashboard/credits`, `/dashboard/admin`, `/editor/<job>`):
`goto` deslogado, esperar, e checar que **nenhum dado sensível** renderiza:
```bash
$B js "/gbbraga|@gmail|999\\.?9|crédito|Olá,/i.test(document.body.innerText) ? 'VAZAMENTO' : 'ok'"
```
PASS = `ok` em todas (ideal: redireciona p/ `/auth/login`). FAIL+bug `alta` se renderizar dado de usuário deslogado.
Nota: em dev a rota pode cair num error boundary (turbopack); o critério de **segurança** é não-vazamento, não o redirect exato. **Re-logar na etapa 2 da próxima iteração.**

**S02 — Security headers**
```bash
curl -s -D - -o /dev/null --max-time 5 http://localhost:8005/health   # backend
curl -s -D - -o /dev/null --max-time 5 http://localhost:3003/         # frontend
```
Esperado no que serve HTML/origem: `x-frame-options`, `x-content-type-options: nosniff`, `referrer-policy`, `strict-transport-security` e idealmente `content-security-policy`.
Baseline conhecido: **backend tem** (nosniff/DENY/HSTS/referrer); **frontend dev NÃO tem nenhum**. PASS local = backend ok. O frontend sem headers é finding `média` — **confirmar em prod** (etapa 6): se `clipia.com.br` também não enviar X-Frame-Options/CSP, abrir bug (clickjacking).

**S03 — Token/secrets não vazam no client** (logado)
```bash
$B js "location.href.includes(localStorage.getItem('clipia_token')||'__x__') ? 'TOKEN_NA_URL' : 'ok'"
$B js "(document.documentElement.outerHTML.match(/sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xai-[A-Za-z0-9]/g)||[]).slice(0,3)"
```
PASS = token nunca na URL **e** zero chaves de API (`sk-`, `AKIA`, etc.) no HTML/DOM. Qualquer chave exposta = bug `alta`.

**S04 — API exige autenticação (sem bypass)**
```bash
for ep in /api/v1/jobs /api/v1/auth/me; do
  curl -s -o /dev/null -w "$ep => %{http_code}\n" --max-time 5 http://localhost:8005$ep
done
```
PASS = todos `401`/`403` sem token (baseline confirmado: ambos `401`). Qualquer `200` sem token = bug `alta`.

**S05 — IDOR / autorização horizontal** (logado)
Acessar um job de UUID aleatório (inexistente/alheio) e confirmar que não retorna dados de outro:
```bash
TK=$($B js "localStorage.getItem('clipia_token')" | tr -d '"')
curl -s -o /dev/null -w "%{http_code}\n" --max-time 5 -H "Authorization: Bearer $TK" \
  http://localhost:8005/api/v1/jobs/00000000-0000-0000-0000-000000000000/composition
```
PASS = `404`/`403` (não `200` com dados). FAIL = bug `alta`.

**S06 — Rate limiting no login (anti brute-force)** — LEVE, máx 8 tentativas, não floodar
```bash
for i in $(seq 1 8); do
  curl -s -o /dev/null -w "%{http_code} " --max-time 5 -X POST http://localhost:8005/api/v1/auth/login \
    -H "Content-Type: application/json" -d '{"email":"qa@test.com","password":"wrong"}'
done; echo
```
PASS = aparece `429` em algum ponto (rate limit ativo). Se 8x `401` sem `429`, finding `média` (sem proteção a brute-force) — confirmar com `tests/test_rate_limiting.py` antes de cravar.

---

## 5. REGISTRAR resultado

Atualize `qa/ralph/QA_LEDGER.md` para o fluxo executado:
- `run_count += 1`, `last_result = PASS|FAIL|BLOCKED`, `last_run = <timestamp>`, anexar achados de console/network se houver.
- Mantenha o histórico dos **3 últimos resultados** por fluxo (ex: `recent: PASS PASS FAIL`).

Se `FAIL`: abra/atualize um bug em `qa/ralph/QA_BUGS.md`:
- **Dedup por assinatura** = `<ID-fluxo> + <sintoma curto>`. Se já existe um bug com a mesma assinatura aberto, só
  incremente o contador de ocorrências e atualize timestamp. Senão crie `BUG-RXXX` (numere sequencial).
- Campos: severidade (alta/média/baixa), reprodução (passos), esperado, observado, evidência (caminho do PNG + linhas de console), status (`open`).
- Se um fluxo que tinha bug aberto passar agora, mude o status do bug para `intermittent` (se às vezes falha) ou `resolved?` (se 3 PASS seguidos).
- Se um fluxo falhar **3x com o mesmo sintoma**, marque o bug como `confirmed` e **continue** (não trave o loop nesse fluxo).

---

## 6. SMOKE PROD (apenas 1x por ciclo, quando `smoke_prod_no_ciclo = não`)

**Read-only — sem login, sem submit, sem geração.** Alvo `https://clipia.com.br`:
```bash
$B goto https://clipia.com.br
$B console --errors        # em PROD deve estar 100% limpo — atenção a React #310 / erro de hidratação
$B is visible "main"       # e confirmar o hero/conteúdo principal renderizou
$B screenshot "$EV/P01-prod-$TS.png"
# P-SEC: headers de segurança em produção (onde de fato importa)
curl -s -D - -o /dev/null --max-time 8 https://clipia.com.br/ | grep -iE 'content-security|x-frame|x-content-type|strict-transport|referrer-policy'
```
Repetir o render+console para `/blog`, `/termos`, `/privacidade`. Registrar P01/P02 no ledger. Setar `smoke_prod_no_ciclo=sim`.
- Se a home prod renderiza branco/erro de hidratação → bug `alta` (regressão de deploy).
- Se prod **não** enviar `x-frame-options`/`content-security-policy` na resposta HTML → bug `média` (clickjacking), pois aqui não há turbopack para justificar. Registrar como `BUG-Rxxx` em `QA_BUGS.md`.

---

## 7. CRITÉRIO DE PARADA (avalie ao fim de cada iteração)

Emita **`<promise>QA GREEN</promise>`** somente se TODAS as condições valerem:
1. Todo fluxo `F01..F13`, `S01..S06` e `P01/P02` tem `run_count ≥ 3`.
2. Os 3 últimos resultados de cada fluxo são todos `PASS`.
3. `qa/ralph/QA_BUGS.md` não tem nenhum bug com status `open` nem `confirmed`.

Se não atingiu → **encerre a iteração sem emitir promise** (o ralph re-injeta o prompt e você continua).
O teto `--max-iterations 50` para o loop de qualquer forma.

---

## Guardrails (regras duras — nunca viole)
- NUNCA deletar conta. NUNCA submeter cadastro/OTP real em loop. NUNCA disparar render real (só abrir a UI do export).
- Em produção: **somente read-only** (sem login, sem submit, sem geração).
- Só **1 geração por ciclo**, sempre **Edge TTS + Stock** (barato), tema sempre prefixado `[QA]`.
- Sempre `localhost`, nunca `127.0.0.1`.
- Evidência obrigatória por fluxo testado: `console --errors` + screenshot. HTTP 200 sozinho não fecha um fluxo como PASS.
- Uma iteração testa **um** fluxo (mais o smoke prod quando o ciclo virou). Não tente varrer tudo numa iteração só.
