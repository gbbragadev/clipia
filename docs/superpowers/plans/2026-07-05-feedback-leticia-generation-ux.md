# Plano: UX de geração — feedback Letícia (temas amplos, coerência tema↔formato)

## Contexto

Feedback de usuária real (Letícia) sobre o fluxo de geração no `/dashboard`:
1. O painel "Em alta agora" parece obrigatório — ela não descobriu que o campo "Tema do vídeo" é texto livre.
2. Os tópicos por nicho (ex.: Finanças) são títulos crus de posts do Reddit em inglês — específicos demais, muitas vezes histórias pessoais.
3. Combinou tópico-história com template "Top Curiosidades" (lista de 5 fatos) → roteiro sem sentido. Não há nenhum acoplamento tema↔template em camada alguma.
4. Ela pediu "temas amplos" por nicho além dos trends — esse dado JÁ EXISTE em `frontend/src/lib/niches.ts` (`exampleTopics`, pt-BR, ~10 por nicho) e só é usado nas páginas SEO `/criar/[nicho]`.

Diagnóstico completo com refs arquivo:linha foi feito em sessão anterior (grounding em 5 leitores).

## Global Constraints (OBRIGATÓRIO para todo implementer)

- **Working tree sujo de OUTRA sessão**: os arquivos `app/config.py`, `app/services/compositor.py`, `app/services/outro.py`, `app/services/subtitles.py`, `app/worker/tasks.py`, `frontend/src/app/globals.css`, `frontend/src/components/landing/**`, `dashboard-mockup.html`, `docs/GUIA-PAGAMENTO-PAINEIS.md`, `docs/ROADMAP-QUALIDADE-VIDEO.md`, `frontend/public/dashboard-mockup.html`, `marketing/**`, `test_sub.ass` estão modificados/untracked por trabalho paralelo. **NUNCA** tocar, stagear, commitar ou reverter esses arquivos. Commits SEMPRE com `git add <caminhos explícitos>` — jamais `git add -A`/`git add .`/`git commit -a`.
- Commit: mensagem via `git commit -F <arquivo temporário>` (hook RTK quebra `-m` em alguns ambientes). Terminar a mensagem com linha `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Strings de UI (frontend): pt-BR **com acentuação correta**.
- Strings de prompt (backend `app/services/scriptwriter.py`): **sem acentos** — seguir a convenção existente do arquivo ("ESTRUTURA OBRIGATORIA", "REGRAS DE NARRACAO").
- Typecheck frontend: `cd frontend && npx next typegen && npx tsc --noEmit` (typegen é obrigatório antes do tsc no Next 16).
- Testes backend: `./.venv312/Scripts/python.exe -m pytest <arquivos do escopo> -q` a partir da raiz do repo. NÃO rodar a suíte inteira (arquivos do worker estão modificados pela outra sessão e podem falhar por causa dela).
- Proibido `as any` / `@ts-ignore`. Sem dependências novas. Ambiente Windows (Git Bash disponível).
- O template/estilo pré-selecionado NUNCA trava a escolha do usuário — é sempre sugestão editável.

## Task 1 — Temas amplos por nicho + template/estilo recomendados no painel "Em alta"

**Arquivos:** `frontend/src/components/dashboard/TrendingPanel.tsx`, `frontend/src/app/dashboard/page.tsx`, `frontend/src/components/dashboard/GenerateForm.tsx`, `frontend/src/lib/niches.ts` (só se precisar de ajuste de tipo).

**Requisitos:**

1. Mudar a interface de seleção do painel de `onSelect(topic: string, trendContext: string)` para um payload único:
   ```ts
   export interface TrendSelection {
     topic: string
     trendContext: string | null
     templateId?: string
     style?: string
   }
   // TrendingPanelProps: onSelect: (sel: TrendSelection) => void
   ```
2. Em `TrendingPanel.tsx`, quando um nicho estiver selecionado (`niche !== null`), renderizar um bloco **"💡 Temas amplos"** entre a fileira de filtros de nicho e a grade de trends:
   - Chips clicáveis (flex-wrap), um por item de `NICHES.find(n => n.slug === niche)!.exampleTopics` (todos os itens, sem cortar).
   - Estilo visual consistente com os chips de nicho existentes (borda `border-white/10`, hover coral), mas distinguível como "clicável para preencher" — usar `rounded-full`, texto `text-xs text-slate-300`.
   - Clique no chip → `onSelect({ topic: <exampleTopic>, trendContext: null, templateId: n.recommendedTemplate, style: n.generateStyle })`.
   - Título do bloco: `💡 Temas amplos` com subtexto pequeno `Assuntos que funcionam sempre — clique para usar.`
   - No feed "🌎 Geral" (niche === null) o bloco NÃO aparece.
3. Botão "Gerar" dos cards de trend passa a enviar também o template/estilo do nicho ativo quando houver: `onSelect({ topic: t.title, trendContext: trendContextOf(t), templateId: nicheDef?.recommendedTemplate, style: nicheDef?.generateStyle })` (no feed Geral, `templateId`/`style` ficam `undefined`).
4. `dashboard/page.tsx`: estado `prefill` passa a guardar o payload completo; repassar a `GenerateForm` como `prefillTopic`, `prefillTrendContext`, `prefillTemplateId`, `prefillStyle`. Manter o `scrollIntoView` existente.
5. `GenerateForm.tsx`: aceitar as duas novas props opcionais. No `useEffect` de prefill existente (hoje linhas ~113-119):
   - quando `prefillTemplateId` vier definido, aplicar via a MESMA lógica de `handleTemplateSelect` (que ajusta `voiceProvider` conforme o template — não duplicar essa lógica; reutilizar a função ou extrair helper) ;
   - quando `prefillStyle` vier definido e for um `StyleValue` válido, `setStyle`.
   - O usuário continua livre para trocar template/estilo depois (nada é travado).
6. Tipagem: `generateStyle` em `niches.ts` deve fluir para `StyleValue` sem cast inseguro. Se `NicheDef.generateStyle` for `string`, restringir o tipo em `niches.ts` para a união de estilos válidos (verificar os valores de `StyleValue` em `StyleSelector.tsx` e os valores usados em `niches.ts` — todos já devem ser válidos) OU validar em runtime no GenerateForm contra a lista de estilos. Preferir restringir o tipo na origem.

**Verificação:** `cd frontend && npx next typegen && npx tsc --noEmit` limpo.

## Task 2 — Copy anti-confusão + campo Tema antes do Template

**Arquivos:** `frontend/src/components/dashboard/TrendingPanel.tsx`, `frontend/src/components/dashboard/GenerateForm.tsx`.

**Requisitos:**

1. `TrendingPanel.tsx`: trocar o subtítulo do painel (hoje: "Temas com tração real nos últimos 30 dias. Clique para gerar um vídeo já fundamentado nos dados.") por:
   `Sugestões com tração real nos últimos 30 dias — use uma como ponto de partida ou escreva seu próprio tema logo abaixo.`
2. `GenerateForm.tsx`: mover o bloco do campo **Tema** (label "Tema do vídeo" + input + `<OpticalBalancePreview …/>`) para ANTES do bloco **Template** (o usuário escolhe o assunto antes do formato). Nenhuma mudança de lógica — só ordem do JSX.
3. Abaixo do label "Tema do vídeo", nada de texto extra; apenas mudar o label para `Tema do vídeo — escreva o que quiser` (mantém a affordance de texto livre explícita, custo zero de layout).

**Verificação:** `cd frontend && npx next typegen && npx tsc --noEmit` limpo.

## Task 3 — Guardrail de adaptação de formato no roteiro (backend)

**Arquivos:** `app/services/scriptwriter.py`, `tests/test_scriptwriter.py`.

**Requisitos (TDD — teste primeiro):**

1. Novo módulo-constante `FORMAT_ADAPT_INSTRUCTION` em `scriptwriter.py` (strings SEM acentos, convenção do arquivo):
   ```python
   FORMAT_ADAPT_INSTRUCTION = """

   ADAPTACAO DE FORMATO:
   - Se o tema NAO se encaixar na estrutura pedida acima (ex.: tema narrativo ou historia pessoal
     com formato de lista de fatos numerados), ADAPTE a estrutura ao tema mantendo o espirito do
     formato (gancho forte, ritmo, CTA).
   - NUNCA invente fatos falsos apenas para preencher o formato.
   - A coerencia do roteiro com o tema tem prioridade sobre a estrutura rigida do formato.
   """
   ```
2. Append de `FORMAT_ADAPT_INSTRUCTION` ao `prompt_text` imediatamente após `prompt_text += template.script.prompt_extra` (aplica a TODOS os templates, incluindo o default), e ANTES do append de `TREND_CONTEXT_INSTRUCTION`.
3. Teste em `tests/test_scriptwriter.py` seguindo o padrão dos testes existentes (mock de `complete_text_ex` capturando o prompt): asserta que o prompt enviado contém `"ADAPTACAO DE FORMATO"` tanto para o template default quanto para `curiosidades_lista`.

**Verificação:** `./.venv312/Scripts/python.exe -m pytest tests/test_scriptwriter.py -q` verde (todos os testes do arquivo, não só o novo).

## Fora de escopo (não fazer)

- Traduzir/filtrar trends do Reddit (fonte EN permanece).
- Gerar subtemas via LLM.
- Mudar as páginas `/criar/[nicho]`.
- Qualquer mudança em arquivos da outra sessão (lista nas Global Constraints).
