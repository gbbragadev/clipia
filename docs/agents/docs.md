# Documentação — Geração por Função/Componente

## Como usar

Cole o código da função/componente ou forneça o arquivo + nome da função. Escolha o tipo de doc.

**Prompt de invocação:**
```
@docs/agents/docs.md
Tipo: docstring-python
Arquivo: app/worker/tasks.py
Função: dispatch_pipeline
```

Tipos disponíveis: `docstring-python`, `jsdoc-component`, `jsdoc-hook`, `endpoint-summary`, `readme-section`

---

## Tipo: docstring-python

Gerar docstring Google Style para a função indicada.

**Formato esperado:**
```python
def minha_funcao(param1: str, param2: int = 0) -> dict:
    """Descrição curta em uma linha.

    Descrição mais longa se necessário (opcional, só se a função
    for complexa ou tiver comportamento não óbvio).

    Args:
        param1: Descrição do parâmetro.
        param2: Descrição. Default: 0.

    Returns:
        Descrição do que retorna. Se dict, listar as chaves principais.

    Raises:
        ValueError: Quando e por quê é lançado.
        HTTPException: Status code e condição.

    Example:
        >>> result = minha_funcao("valor", 42)
    """
```

**Regras:**
- Primeira linha: verbo no imperativo, max 72 chars, sem ponto final
- Não documentar parâmetros óbvios pelo nome (`user_id: ID do usuário` é redundante)
- `Raises` só quando a função tem raises explícitos
- `Example` só para funções de utilidade com uso não óbvio

---

## Tipo: jsdoc-component

Gerar JSDoc para componente React.

**Formato esperado:**
```tsx
/**
 * Exibe o formulário de geração de vídeo com validação inline.
 *
 * Debita 1 crédito ao submeter. Requer email verificado.
 *
 * @param onSuccess - Callback chamado após job criado com sucesso
 * @param disabled - Desabilita o formulário (ex: sem créditos)
 *
 * @example
 * <GenerateForm onSuccess={(jobId) => router.push(`/editor/${jobId}`)} />
 */
```

**Regras:**
- Descrever o que o componente faz para o usuário, não como implementa
- Documentar props não óbvias (omitir `className?: string`)
- Mencionar side effects relevantes (debita crédito, faz chamada de API)

---

## Tipo: jsdoc-hook

Gerar JSDoc para custom hook React.

**Formato esperado:**
```tsx
/**
 * Gerencia o estado de autenticação e operações de sessão.
 *
 * @returns
 * - `user` - Dados do usuário autenticado, ou null se não logado
 * - `loading` - True enquanto verifica sessão inicial
 * - `logout` - Função que limpa token e redireciona para /auth/login
 *
 * @example
 * const { user, loading } = useAuth()
 * if (loading) return <Spinner />
 * if (!user) redirect('/auth/login')
 */
```

---

## Tipo: endpoint-summary

Gerar summary + description para endpoint FastAPI.

**Formato esperado:**
```python
@router.post(
    "/generate",
    summary="Gerar vídeo curto",
    description="""
Cria um novo job de geração de vídeo a partir de um tema.

- Requer email verificado
- Debita 1 crédito imediatamente
- Inicia pipeline assíncrono (Celery)
- Retorna `job_id` para polling via `/jobs/{job_id}/status`
""",
    responses={
        200: {"description": "Job criado. Retorna job_id e status inicial."},
        402: {"description": "Créditos insuficientes."},
        403: {"description": "Email não verificado."},
        429: {"description": "Rate limit: máx 10 req/min."},
    },
    tags=["Vídeos"],
)
```

**Regras:**
- `summary`: máx 5 palavras, verbo no infinitivo
- `description`: listar comportamentos relevantes como bullet points
- `responses`: só documentar os que realmente podem acontecer

---

## Tipo: readme-section

Gerar seção de README para uma feature ou módulo.

**Input esperado:** nome do módulo/feature + para quem é o README (dev interno, usuário final, API consumer)

**Formato esperado:**
```markdown
## [Nome do módulo]

[1-2 frases: o que faz e por que existe]

### Como usar

[Exemplo mínimo funcional]

### Referência

| Campo | Tipo | Descrição |
|-------|------|-----------|
| ... | ... | ... |

### Observações

- [Gotcha ou comportamento não óbvio]
```

---

## Regras gerais

- Escrever em português apenas se o código-base do projeto estiver em português (não é o caso aqui — usar inglês para código, português para copy de UI)
- Docstrings e JSDoc: inglês
- Não inventar comportamento — se não tiver certeza, marcar com `# TODO: verificar`
- Não alterar o código, apenas gerar a documentação para inserir
