# Gemini Flash Agents — Design Spec
**Data:** 2026-04-05
**Status:** Aprovado

## Contexto

O projeto ClipIA já possui `GEMINI_TASKS.md` e `GEMINI_FRONTEND_REDESIGN.md` escritos para **Gemini 3 Pro** (modelo mais capaz): escopo amplo, múltiplos arquivos, julgamento autônomo. Este spec define uma camada complementar de agentes para **modelos Flash** (Gemini 2.5 Flash / Gemini 3 Flash) — menos capazes, mas rápidos e baratos. Modelos Flash são usados via Gemini CLI, que carrega `GEMINI.md` automaticamente.

## Problema

Modelos Flash falham quando a tarefa é:
- Aberta demais ("leia todos os .tsx e corrija")
- Exige múltiplas decisões encadeadas
- Requer julgamento arquitetural

Precisam de tarefas atômicas: um arquivo, uma saída, um formato esperado.

## Decisão de Design

### Estrutura de arquivos

```
GEMINI.md                        ← reescrito: config de agente Flash
docs/agents/
  qa.md                          ← QA por arquivo/componente
  security.md                    ← audit de segurança por vetor
  docs.md                        ← docstrings/JSDoc por função
  marketing.md                   ← copy por componente
  planning.md                    ← quebrar tarefa → subtarefas
```

### GEMINI.md reformulado

Não é mais só contexto de projeto (isso fica no `GEMINI.md` atual como base). É config de agente com:
- **Papel**: executor de tarefas seguras, planejador de subtarefas, gerador de análises
- **Regras de segurança** (hard):
  - ✅ Pode executar autonomamente: escrever docs, testes, copy, relatórios, adicionar comentários, gerar arquivos novos de análise
  - ⚠️ Deve perguntar antes: mudanças em arquivos de auth, config, migrations, qualquer delete
  - ❌ Nunca toca: `.env`, `alembic/`, `docker-compose.yml`, `CLAUDE.md`, `GEMINI.md`
- **Routing por modelo**: 2.5 Flash para contexto longo (lê arquivo inteiro), 3 Flash para geração rápida (recebe trecho, produz output)

### Princípio dos task files

Cada arquivo em `docs/agents/` segue o padrão:

```markdown
## Tarefa: [Nome]
**Modelo recomendado:** Gemini 2.5 Flash | 3 Flash
**Input:** O que o usuário passa (arquivo, trecho, nome de função)
**Output esperado:** Exatamente o que deve ser produzido
**Formato da saída:** [especificado]
**Verificação:** Comando para confirmar que não quebrou nada
```

Nunca: "leia tudo e decida o que fazer". Sempre: "dado X, produza Y no formato Z".

### Divisão de responsabilidades: Flash vs Pro

| Tipo de tarefa | Gemini Pro (existente) | Gemini Flash (este spec) |
|---|---|---|
| QA | Varredura completa de todos os .tsx | Checklist em um componente específico |
| Segurança | Análise geral do projeto | Um vetor por vez (ex: só CORS, só SQL) |
| Docs | Documenta todos os endpoints | Docstring de uma função/endpoint |
| Marketing | Reescreve landing inteira | Headline alternativo, microcopy de um componente |
| Planejamento | Decide arquitetura | Quebra tarefa em lista de passos |

## Arquivos a criar/modificar

1. **`GEMINI.md`** — reescrever (preservar contexto de projeto, adicionar config de agente)
2. **`docs/agents/qa.md`** — novo
3. **`docs/agents/security.md`** — novo
4. **`docs/agents/docs.md`** — novo
5. **`docs/agents/marketing.md`** — novo
6. **`docs/agents/planning.md`** — novo

## O que NÃO está no escopo

- Integração via API (não é código, são prompts/configs)
- Modificar `GEMINI_TASKS.md` ou `GEMINI_FRONTEND_REDESIGN.md` (são para Pro, permanecem intactos)
- Criar automações de cron/schedule (isso é outra sessão)

## Critério de sucesso

Gui consegue abrir o Gemini CLI no diretório do projeto e dizer "execute a tarefa de QA no arquivo X" sem precisar explicar contexto — o Gemini lê o `GEMINI.md`, entende o papel dele, e executa de forma atômica sem quebrar nada.
