# Sessão Autônoma — Prompts de Kickoff

Cole um dos prompts abaixo no início da sessão Gemini CLI.
O GEMINI.md já é carregado automaticamente — não precisa referenciá-lo.

---

## QA — varredura de um diretório

```
Leia @docs/agents/qa.md.

Execute o checklist em TODOS os arquivos .tsx de `frontend/src/components/dashboard/`.
Para cada arquivo, aplique o checklist completo e gere um relatório consolidado no formato especificado.
Não corrija nada — apenas reporte.
Ao terminar, crie o arquivo `docs/reports/qa-dashboard-<DATA>.md` com o relatório completo.
```

---

## Segurança — audit completo por vetor

```
Leia @docs/agents/security.md.

Execute os vetores abaixo em sequência, um por vez:
1. cors — arquivo: app/main.py
2. jwt — arquivos: app/auth/
3. sql — arquivos: app/services/, app/api/routes.py
4. inputs — arquivos: app/api/routes.py, app/models.py
5. auth-frontend — arquivos: frontend/src/lib/auth.ts
6. secrets — todo o repositório
7. rate-limit — arquivos: app/main.py, app/api/routes.py
8. webhook — arquivos: app/payments/

Para cada vetor, gere o relatório no formato especificado.
Consolide tudo em `docs/reports/security-audit-<DATA>.md` ao final.
Não corrija nada — apenas reporte.
```

---

## Documentação — todos os endpoints

```
Leia @docs/agents/docs.md.

Para cada endpoint em `app/api/routes.py`, gere:
- summary e description no formato FastAPI
- responses documentados (4xx relevantes)

Depois, para cada função pública em `app/services/`, gere docstring Google Style.

Não altere os arquivos — gere o resultado como patches no formato:

ARQUIVO: app/api/routes.py
FUNÇÃO: generate_video
ADICIONAR:
```python
[código gerado]
```

Ao terminar, salve tudo em `docs/reports/docs-patches-<DATA>.md`.
```

---

## Marketing — revisão completa da landing

```
Leia @docs/agents/marketing.md.

Leia os componentes:
- frontend/src/components/hero/HeroSection.tsx
- frontend/src/components/SocialProofBar.tsx
- frontend/src/components/ShowcaseSection.tsx

Para cada componente:
1. Identifique todos os textos visíveis para o usuário
2. Execute a tarefa `microcopy` para avaliar cada texto
3. Para textos de headline/CTA, execute também `headline-alternativo` ou `cta-alternativo`

Gere um relatório em `docs/reports/copy-review-<DATA>.md` com o texto atual e sugestões.
Não altere os arquivos.
```

---

## Planning — próxima feature

```
Leia @docs/agents/planning.md.

Feature a planejar: [DESCREVA AQUI]

Gere o plano completo no formato especificado.
Salve em `docs/plans/plan-[nome-feature]-<DATA>.md`.
```

---

## Dica de uso

Para sessões longas, adicione ao final do prompt:

```
Execute de forma autônoma. Só me interrompa se precisar de uma decisão
que não está coberta pelas regras de segurança do GEMINI.md.
Ao final de cada tarefa, confirme o que foi feito antes de avançar para a próxima.
```
