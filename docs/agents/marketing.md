# Marketing — Copy por Componente

## Como usar

Forneça o componente ou texto atual + a tarefa específica. Sempre uma peça por vez.

**Prompt de invocação:**
```
@docs/agents/marketing.md
Tarefa: headline-alternativo
Componente: HeroSection
Headline atual: "Crie vídeos curtos com IA"
```

Tarefas disponíveis: `headline-alternativo`, `cta-alternativo`, `microcopy`, `social-post`, `email-assunto`, `descrição-funcionalidade`

---

## Contexto do produto (sempre considerar)

**ClipIA** — plataforma SaaS brasileira que gera vídeos curtos (Shorts/Reels/TikTok) automaticamente com IA. O usuário digita um tema, a IA cria roteiro, narração em pt-BR, legendas sincronizadas e vídeo pronto.

**Proposta de valor:** vídeo pronto em 2 minutos, sem saber editar, em português.

**Público:** criadores de conteúdo brasileiros, social media managers, educadores.

**Preços:** 2 vídeos grátis. Pacotes: Starter 10 vídeos/R$19,90 | Popular 30/R$49,90 | Pro 100/R$129,90.

**Tom de voz:**
- Direto e confiante (sem superlativos vazios)
- Benefício antes de feature
- "Você" (não "tu", não "vocês")
- Urgência sutil, não agressiva
- Nunca: "revolucionário", "incrível", "o melhor"
- Sempre: pt-BR correto com acentos

---

## Tarefa: headline-alternativo

Gerar 5 alternativas para o headline fornecido.

**Formato:**
```
1. [Headline] — [por que funciona em 1 frase]
2. ...
```

**Critérios de qualidade:**
- Máx 8 palavras
- Benefício concreto, não feature
- Funciona sem contexto (alguém que não conhece o produto entende o valor)
- Sem ponto final
- Sem emojis

---

## Tarefa: cta-alternativo

Gerar 5 alternativas para o texto de botão/CTA fornecido.

**Formato:**
```
1. [Texto do CTA] — [contexto de uso ideal]
2. ...
```

**Critérios:**
- Verbo no imperativo
- Máx 5 palavras
- Específico (não "Clique aqui", não "Saiba mais")
- Orientado à ação do usuário, não do sistema

---

## Tarefa: microcopy

Melhorar textos de suporte da UI: placeholders, labels, mensagens de erro, tooltips, banners.

**Input:** cole o texto atual e onde aparece na UI.

**Output:** versão melhorada + explicação de 1 linha.

**Critérios:**
- Mensagens de erro: descrevem o problema E a ação a tomar
- Placeholders: exemplo real, não "Digite aqui"
- Tooltips: 1 frase, sem redundância com o label
- Banners/alertas: urgência proporcional à gravidade

---

## Tarefa: social-post

Gerar post para divulgar uma feature ou resultado do ClipIA.

**Input:** feature/resultado a divulgar + plataforma (Twitter/X, LinkedIn, Instagram caption)

**Formato por plataforma:**

**Twitter/X:**
- Máx 280 chars
- Opcional: 1 emoji estratégico
- Sem hashtags genéricas
- Call to action com link no final

**LinkedIn:**
- 3-5 parágrafos curtos
- Começa com hook (pergunta ou fato surpreendente)
- Tom mais profissional
- Hashtags relevantes no final (3-5)

**Instagram caption:**
- Primeira linha é o hook (aparece antes do "ver mais")
- Emojis OK mas com moderação
- CTA no final ("Link na bio")
- Hashtags em bloco separado por linha em branco

---

## Tarefa: email-assunto

Gerar 5 opções de assunto para o email indicado.

**Input:** tipo de email (boas-vindas, compra confirmada, vídeo pronto, etc.)

**Formato:**
```
1. [Assunto] — [taxa de abertura esperada: alta/média] — [por quê]
2. ...
```

**Critérios:**
- Máx 50 chars (para não cortar em mobile)
- Personalização com {nome} quando faz sentido
- Emojis só no início ou no final, nunca no meio
- Sem caps lock
- A/B test: misturar approaches (pergunta, benefício, número, urgência)

---

## Tarefa: descrição-funcionalidade

Descrever uma feature do ClipIA para página de produto, onboarding ou documentação.

**Input:** nome da feature + para qual audiência (usuário final, desenvolvedor, investidor)

**Formato:**
```
TÍTULO: [nome da feature]
DESCRIÇÃO CURTA: [1 frase — para cards, tooltips]
DESCRIÇÃO MÉDIA: [2-3 frases — para página de produto]
BENEFÍCIO PRINCIPAL: [o que o usuário ganha]
DIFERENCIAL: [por que isso importa para o ClipIA especificamente]
```
