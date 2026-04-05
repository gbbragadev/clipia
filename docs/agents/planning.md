# Planejamento — Quebrar Tarefa em Subtarefas

## Como usar

Descreva a tarefa ou feature que quer implementar. O Gemini quebra em subtarefas atômicas e ordenadas.

**Prompt de invocação:**
```
@docs/agents/planning.md
Tarefa: Implementar sistema de notificações push quando vídeo ficar pronto
```

---

## O que o Gemini faz

1. **Identifica dependências** — o que precisa existir antes
2. **Quebra em subtarefas atômicas** — cada uma deve ser completável em ~30 min
3. **Classifica por camada** — backend, frontend, infra, testes
4. **Sinaliza riscos** — o que pode dar errado ou precisar de mais investigação
5. **Sugere ordem de execução** — do mais simples ao mais complexo

---

## Formato de saída

```markdown
## [Nome da Feature]

### Dependências
- O que precisa estar pronto antes: [lista]
- Investigar antes de começar: [lista]

### Subtarefas

**Camada: Backend**
- [ ] [Subtarefa 1] — [arquivo provável] — [~tempo estimado]
- [ ] [Subtarefa 2] — ...

**Camada: Frontend**
- [ ] [Subtarefa 1] — [componente provável] — [~tempo estimado]

**Camada: Testes**
- [ ] [Teste 1] — [arquivo de teste]

**Camada: Infra/Config** (se aplicável)
- [ ] [Item de config/env/deploy]

### Riscos identificados
- ⚠️ [Risco 1]: [por quê e como mitigar]

### Ordem sugerida
1. [Subtarefa X] — porque é a base
2. [Subtarefa Y] — depende de X
3. ...
```

---

## Regras para o Gemini

- **Atômico**: cada subtarefa deve ser completável e testável de forma independente
- **Concreto**: nomear o arquivo/componente provável, não apenas "criar endpoint"
- **Sem gold plating**: incluir apenas o que a feature descrita requer
- **Riscos reais**: só listar riscos que realmente podem acontecer neste projeto, não genéricos

---

## Contexto do projeto para o planejamento

**Onde adicionar código:**
- Novo endpoint → `app/api/routes.py` ou novo arquivo em `app/api/`
- Nova task Celery → `app/worker/tasks.py`
- Lógica de negócio → `app/services/`
- Novo modelo de dados → `app/models.py` + migration em `alembic/`
- Novo componente → `frontend/src/components/`
- Nova página → `frontend/src/app/[rota]/page.tsx`
- Novo hook → `frontend/src/lib/` ou `frontend/src/hooks/`
- Novos testes → `tests/test_<feature>.py`

**Restrições conhecidas:**
- Worker Celery precisa restart após mudar assinatura de tasks
- TTS async no FastAPI: usar `synthesize_narration_async()`, não a versão sync
- Whisper precisa do preload de CUDA libs (ver CLAUDE.md)
- Remotion Player carregado com dynamic import SSR:false
