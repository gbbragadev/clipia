# UX Audit F0 — App logado ClipIA (walkthrough de persona)

> Data: 10/07/2026 · Método: persona walkthrough (LIFT/Fogg) + captura headless logada
> (conta admin de teste, prod local 3003, viewports 1440×900 e 390×844).
> Screenshots: `frontend/F0-*.png` (01-11). Nota: simulação qualitativa — hipóteses
> fortes, não estatística. Ações pagas NÃO foram exercitadas (ficam para a F5 com
> conferência de débito/estorno).

**Persona**: "Criador sem rosto" que acabou de pagar R$ 49,90 (pacote Popular). Canal de
curiosidades. Quer: gerar o vídeo do dia em minutos e confiar que o crédito rende.
Medos: gastar crédito à toa; ferramenta "gringa" que não entende pt-BR.

---

## Tela 1 — Dashboard, primeira dobra (F0-01)

**Persona:** "Bom dia, admin. Bonito. Mas... isso é um feed de notícia? 'TIL that after
Christopher Eccleston'... tá em inglês. 'EU Parliament greenlights Chat Control'? Eu vim
GERAR vídeo. Cadê o campo de criar? [scroll] Ah, tá lá embaixo."

**Analista:**
- LIFT Relevance ↓↓: o painel "Em alta" ocupa a primeira dobra INTEIRA com tendências
  Reddit/HN **em inglês** e itens sem contexto ("mega 3029"). Para o ICP BR é ruído.
- Fogg: Motivation alta (acabou de pagar), Ability ↓ (ação primária abaixo do fold),
  Prompt fraco (nenhum CTA "criar" visível sem scroll).
- Roxo residual VIVO: FAB do FeedbackWidget é roxo/rosa (fora da paleta).
- Botão "Gerar" repetido 10× na dobra (distração; todos iguais).

**Recomendações (→F2):** inverter hierarquia — formulário de geração no topo (é a
promessa "digite o tema"), "Em alta" vira faixa compacta/colapsável ao lado ou abaixo;
traduzir/filtrar tendências para pt-BR no backend (ou rotular idioma e priorizar fontes
BR); FAB do feedback na paleta.

## Tela 2 — GenerateForm (F0-02, sessão anterior LIVE-dashboard-studio)

**Persona:** "Ok, achei. Tema, template, estilo... muita coisa de uma vez, mas dá. '1
crédito será usado · 9998 disponíveis' — gostei, sei o que gasto. O botão tá cinza e não
diz por quê."

**Analista:** custo antes da ação = ✅ (padrão a replicar). Botão desabilitado sem hint
(Fogg Ability ↓). "Roteiro avancado" sem acento. Formulário monolítico (aceitável com
hierarquia melhor; não quebrar em wizard — criador quer velocidade).

## Tela 3 — Seus vídeos (F0-03)

**Persona:** "Cadê meus vídeos... esses retângulos coloridos são os vídeos? Não tem NEM
IMAGEM do vídeo. Vejo três por tela. Pra achar o de ontem vou rolar a vida."

**Analista:**
- Cards 9:16 gigantes SEM thumbnail (gradiente + nada) = a maior dívida visual do app.
  21 vídeos ≈ 7 telas de rolagem. Densidade baixíssima, zero informação visual.
- Status "PRONTO" verde fora da paleta (emerald hardcoded).
- Filtros ok mas redundantes com tão pouca densidade.

**Recomendações (→F2):** thumbnail real do MP4 (backend FFmpeg no finalize) + cards
menores (4-5 por linha desktop) + StatusBadge semântico pt-BR nos tokens.

## Tela 4 — Credits (F0-04)

**Persona:** "Essa tela é boa. Saldo grandão, +20% de bônus, Pix. 'R$ 1,39 por crédito'
no Popular... na página de venda dizia R$ 1,66 por vídeo. Qual é a conta certa?"

**Analista:**
- Melhor tela do app logado — MAS: badge "Melhor custo" ROXA e CTA "Comprar" do Popular
  em gradiente **coral→roxo** (o gradiente antigo `btn-primary`). Roxo vivo na tela de
  DINHEIRO.
- Inconsistência de narrativa de preço com a landing (por crédito c/ bônus vs por vídeo
  s/ bônus). LIFT Clarity ↓ / Anxiety ↑ na hora da compra.
- Histórico com "Pendente" âmbar ok.

**Recomendações (→F4):** matar roxo; alinhar a métrica com a landing ("≈ R$ X,XX por
vídeo com voz padrão", bônus como chip mint); explicar "Pendente" (Pix aguarda ~min).

## Tela 5 — Editor desktop (F0-07/08/09)

**Persona:** "Abriu rápido, meu vídeo tá aí. O lado direito é claro. Mas que MAR de
espaço vazio em volta do vídeo. Embaixo tem uns blocos coloridos... 1 é laranja, 2 é
azul, 3 verde... o que significam as cores? 'home office challenge'?? Por que os chips da
minha cena estão em inglês? Na aba Voz: 'Regerar narração' — isso gasta crédito? Não diz."

**Analista:**
- Header/abas já corais ✅; estados salvo/dirty ✅.
- Workspace: player com enorme área morta à esquerda (painel 320px fixo à direita);
  timeline com cores ARBITRÁRIAS por cena (sem semântica — deveria ser neutra com accent
  só na ativa); palavras da legenda na timeline ilegíveis.
- Keywords de cena em inglês (vêm do pipeline) expostas na UI.
- **Custo invisível**: "Regerar narração" (gradiente coral→roxo antigo!) sem custo; AI
  Suggest sem custo; tabs de voz mostram custo ✅ (Premium 2cr, Minha Voz 1cr).
- "Carregando vozes..." persistente na aba Voz (lento/estado pendurado).
- "voz unica" sem acento.

**Recomendações (→F3):** CostChip padrão nas 4 ações pagas; gradiente roxo → coral
sólido; timeline neutra (cena ativa coral, resto panel-2/3); esconder/traduzir keywords;
aproveitar área morta (player maior ou painel de contexto).

## Tela 6 — Editor mobile (F0-11)

**Persona:** "No celular tá até melhor que no PC. Player em cima, cenas embaixo. O botão
'Linha do tempo' fica em cima do texto da cena 3."

**Analista:** reflow funciona ✅; FAB sobrepõe conteúdo no fim do scroll (falta
padding-bottom na lista ≥ altura do FAB); undo/redo no header ✅.

## Console (todas as telas)
Sem erros JS. Warnings de preload de fonte (pré-existentes, baixa prioridade — corrigir
`as`/preload na F1 se trivial). 404 pontuais de asset de preview em cards antigos
(investigar na F2 com o thumbnail).

---

## Top 8 prioridades da auditoria (ordem de impacto na confiança/conversão)

1. Thumbnail real nos VideoCards + densidade da grid (F2) — a cara do produto logado.
2. Hierarquia do dashboard: gerar em cima, "Em alta" compacto (F2).
3. Tendências em pt-BR/filtradas (F2 backend) — relevância para o ICP.
4. Custo visível nas 4 ações pagas do editor + matar gradiente roxo (F3).
5. Roxo na tela de credits (badge + CTA) e FAB de feedback (F1/F4).
6. Timeline com cor semântica + legibilidade (F3).
7. Narrativa de preço única landing↔credits (F4).
8. FAB mobile sobre conteúdo + hints de botão desabilitado + acentos (F2/F3/F4).
