# QA — Checklist por Arquivo

## Como usar

Forneça o caminho do arquivo que quer checar. O Gemini lê o arquivo e aplica os checklists abaixo que forem relevantes para o tipo de arquivo.

**Prompt de invocação:**
```
@docs/agents/qa.md
Arquivo: frontend/src/components/dashboard/GenerateForm.tsx
```

---

## Checklist: Componente React (.tsx)

Para cada item, reportar: ✅ OK | ⚠️ Problema | ➖ Não se aplica

### Estados
- [ ] Tem estado de loading quando faz chamada async?
- [ ] Tem estado de erro com mensagem útil para o usuário?
- [ ] Tem estado vazio (empty state) quando lista está vazia?
- [ ] Botões ficam desabilitados durante loading?
- [ ] Formulários limpam erros ao digitar novamente?

### Acessibilidade
- [ ] Botões com só ícone têm `aria-label`?
- [ ] Imagens têm `alt` text?
- [ ] Inputs têm `label` associado (htmlFor) ou `aria-label`?
- [ ] Erros de formulário estão associados ao campo com `aria-describedby`?

### Idioma
- [ ] Todo texto visível para o usuário está em pt-BR?
- [ ] Mensagens de erro estão em pt-BR e descrevem a ação a tomar?
- [ ] Nenhum texto em inglês hardcoded visível para o usuário?

### Dark mode / Tailwind
- [ ] Cores usam `dark:` variant quando necessário?
- [ ] Sem cores hardcoded inline (style={{color: '...'}}) que ignoram o tema?

### TypeScript
- [ ] Props têm tipos definidos (interface ou type)?
- [ ] Sem `any` explícito?
- [ ] Retornos de API têm tipo ou cast explícito?

---

## Checklist: Endpoint Python (routes.py)

### Segurança
- [ ] Endpoint autenticado tem `current_user` como dependência?
- [ ] Valida que o recurso pertence ao usuário antes de retornar/modificar?
- [ ] Inputs passam por Pydantic model (não aceita dict cru)?

### Erros
- [ ] Retorna HTTP 4xx correto para erros de cliente (não 500)?
- [ ] Mensagens de erro não expõem stack trace ou informação interna?
- [ ] Caso de "não encontrado" retorna 404, não 200 vazio?

### Documentação
- [ ] Endpoint tem `summary` no decorator?
- [ ] Parâmetros de path/query têm descrição?
- [ ] Responses de erro estão documentadas?

---

## Formato do relatório

Para cada problema encontrado:
```
ARQUIVO: <caminho>
LINHA: ~<número aproximado>
CHECKLIST: <categoria>
PROBLEMA: <descrição curta>
SUGESTÃO: <como corrigir>
SEVERIDADE: alta | média | baixa
```

Ao final: resumo com contagem por severidade.

**Não corrija automaticamente.** Apenas reporte.
