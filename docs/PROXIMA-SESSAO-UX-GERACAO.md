# Próxima sessão — UX de geração (continuação do feedback da Letícia)

> Escrito em 06/07/2026 ao fim da sessão que analisou e corrigiu o feedback da Letícia.
> Contexto completo: `docs/superpowers/plans/2026-07-05-feedback-leticia-generation-ux.md` (plano executado)
> e memória `feedback-leticia-generation-ux.md`.

## Estado ao fim da sessão (tudo NO AR)

- **5 commits** em `feat/editor-mobile-ux` (`b41f7f8..1a54af8`), review whole-branch "ready to merge":
  1. "💡 Temas amplos" por nicho no painel Em alta (chips dos `exampleTopics` de `niches.ts`) + seleção pré-sugere `recommendedTemplate`/`generateStyle` do nicho.
  2. Prefill com guarda por EVENTO (`${topic}|${templateId}` em ref; espera `templates` carregar; override manual persiste até a próxima seleção).
  3. Copy: painel explicitamente opcional; "Tema do vídeo — escreva o que quiser" ANTES do Template.
  4. Backend: `FORMAT_ADAPT_INSTRUCTION` no scriptwriter (LLM adapta estrutura a tema incompatível). 18/18 testes.
- **Deploy 06/07 00:00**: frontend rebuild (BUILD_ID `ibtDPnVBZG5xo-trLrV0Z`) + worker respawnado.
  Smoke headless verde: home sem erro de console; dashboard logado → nicho Histórias → chip preenche tema,
  Story Time auto-seleciona, Tema antes do Template (screenshot na sessão).

## Próximos passos (priorizados)

1. **Fechar o loop com a Letícia** — pedir para ela re-testar o fluxo (finanças → Temas amplos → gerar). O guardrail
   de formato é instrução de prompt: só um vídeo real prova a qualidade. Critério: vídeo coerente com tema-história.
2. **Trends pt-BR** (v2 do painel): os cards de trend seguem em INGLÊS cru (títulos de posts do Reddit —
   `app/services/trends.py:39-47`). Traduzir/reescrever como tema de vídeo via LLM barato dentro do `fetch_trends`
   (cache Redis de 4h já existe → custo ~1 chamada/nicho/4h). Manter `context` original para o roteiro.
3. **Coerência trend→template**: post narrativo (r/tifu, r/stories) sugerindo `curiosidades_lista` continua possível
   se o usuário trocar manualmente; avaliar classificar o trend (história vs fato) e ajustar a sugestão.
4. **Subtemas dinâmicos**: hoje os Temas amplos são os 10 `exampleTopics` estáticos por nicho; gerar variações via
   LLM (mesmo cache do trends) se os estáticos "gastarem".
5. **BLOCO A restante** (roadmap produto, memória `golive-roadmap-produto-monetizacao`): UX de roteiro no fluxo,
   baixar/assistir melhorados, mais templates.

## Gotchas desta sessão (não re-aprender)

- Working tree compartilhado com outras sessões: staging SEMPRE por caminho explícito; nunca `git add -A`.
- `git commit -F` com tempfile escrito por PowerShell insere BOM na mensagem → escrever o tempfile no Git Bash.
- `restart-frontend.ps1` tem bug cosmético (`$home` é read-only no PS) — a validação de chunks é a que vale.
- Smoke logado: JWT via `create_access_token` de `app.auth.service` (tabela `users` NÃO tem coluna `is_admin`),
  `localStorage clipia_token`, browse do gstack (`~/.claude/skills/gstack/browse/dist/browse.exe`).
- Cliques no dashboard/editor podem disparar ações que custam créditos — smoke só em prefill, nunca no submit.

## Prompt para a próxima sessão (colar e ajustar o objetivo)

```
Continuação da UX de geração do ClipIA (branch feat/editor-mobile-ux). Leia primeiro:
- docs/PROXIMA-SESSAO-UX-GERACAO.md (estado + gotchas)
- docs/superpowers/plans/2026-07-05-feedback-leticia-generation-ux.md (o que já foi feito)

Contexto: o feedback da Letícia (trends "obrigatórios", tópicos EN específicos demais, formato incoerente
com tema) foi corrigido e está NO AR (temas amplos por nicho, prefill de template/estilo por evento,
guardrail ADAPTACAO DE FORMATO no scriptwriter, smoke verde).

Objetivo desta sessão: [ESCOLHER: (a) trends pt-BR — reescrever títulos EN como temas de vídeo em pt-BR
via LLM barato dentro do fetch_trends, aproveitando o cache Redis de 4h; (b) validar com vídeo real o
guardrail de formato (tema-história + template curiosidades) e ajustar o prompt se necessário; (c) outro
item do BLOCO A do roadmap].

Regras: trabalhar na feat/editor-mobile-ux; staging por caminho explícito (tree compartilhado); commits
com git commit -F (tempfile via Git Bash, nunca PowerShell); testes backend só nos arquivos do escopo;
frontend valida com npx next typegen && npx tsc --noEmit; deploy = restart-frontend.ps1 -Rebuild +
kill do celery (loop respawna); validar em runtime com o browse do gstack (HTTP 200 não basta).
```
