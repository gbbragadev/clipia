# QA Report — Dashboard Components (2026-04-05)

## Arquivos analisados em `frontend/src/components/dashboard/`

### ARQUIVO: `frontend/src/components/dashboard/VideoCard.tsx`
- **LINHA:** ~85
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Ícone de play no overlay não tem `aria-hidden="true"`.
  **SUGESTÃO:** Adicionar `aria-hidden="true"` ao SVG.
  **SEVERIDADE:** baixa
- **LINHA:** ~113
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** SVG de duração não tem `aria-hidden="true"`.
  **SUGESTÃO:** Adicionar `aria-hidden="true"` ao SVG.
  **SEVERIDADE:** baixa
- **LINHA:** ~125
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Botões de ação (Edit/Download) só aparecem no hover, o que dificulta navegação por teclado e dispositivos touch.
  **SUGESTÃO:** Garantir que as ações sejam acessíveis via foco de teclado (ex: `group-focus-within:opacity-100`).
  **SEVERIDADE:** média
- **LINHA:** ~10
  **CHECKLIST:** Dark mode / Tailwind
  **PROBLEMA:** Cores hardcoded no objeto `STYLE_GRADIENTS`.
  **SUGESTÃO:** Usar variáveis de tema ou garantir que as cores funcionam bem em ambos os temas.
  **SEVERIDADE:** baixa

---

### ARQUIVO: `frontend/src/components/dashboard/DashboardNavbar.tsx`
- **LINHA:** ~12
  **CHECKLIST:** Dark mode / Tailwind
  **PROBLEMA:** Uso excessivo de `style={{ background: ... }}` com hex codes.
  **SUGESTÃO:** Substituir por classes Tailwind que respeitem o tema ou usar variáveis CSS globais.
  **SEVERIDADE:** média
- **LINHA:** ~20
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Link do Logo não tem `aria-label`.
  **SUGESTÃO:** Adicionar `aria-label="Ir para home"`.
  **SEVERIDADE:** baixa

---

### ARQUIVO: `frontend/src/components/dashboard/UserDropdown.tsx`
- **LINHA:** ~30
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Botão de trigger (avatar) não tem `aria-label`.
  **SUGESTÃO:** Adicionar `aria-label="Menu do usuário"`.
  **SEVERIDADE:** média
- **LINHA:** ~37
  **CHECKLIST:** Dark mode / Tailwind
  **PROBLEMA:** Múltiplos blocos de `style` com hex codes e variáveis manuais.
  **SUGESTÃO:** Migrar para classes utilitárias do Tailwind.
  **SEVERIDADE:** baixa
- **LINHA:** ~90
  **CHECKLIST:** Idioma
  **PROBLEMA:** "Dashboard" poderia ser traduzido para "Painel" para consistência com o idioma pt-BR.
  **SUGESTÃO:** Alterar para "Painel".
  **SEVERIDADE:** baixa

---

### ARQUIVO: `frontend/src/components/dashboard/GenerateForm.tsx`
- **LINHA:** ~125
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Label "Tema do vídeo" não está associada ao input via `htmlFor`.
  **SUGESTÃO:** Adicionar `id` ao input e `htmlFor` ao label.
  **SEVERIDADE:** média
- **LINHA:** ~147
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Label "Duração" não está associada ao input via `htmlFor`.
  **SUGESTÃO:** Adicionar `id` ao input e `htmlFor` ao label.
  **SEVERIDADE:** média
- **LINHA:** ~163
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Botão de "Roteiro avancado" não tem `aria-expanded` para indicar estado do toggle.
  **SUGESTÃO:** Adicionar `aria-expanded={showAdvancedScript}`.
  **SEVERIDADE:** média
- **LINHA:** ~166
  **CHECKLIST:** Idioma
  **PROBLEMA:** Texto "Roteiro avancado" sem acento.
  **SUGESTÃO:** Alterar para "Roteiro avançado".
  **SEVERIDADE:** baixa
- **LINHA:** ~102
  **CHECKLIST:** Idioma
  **PROBLEMA:** "Video enfileirado", "A geracao foi iniciada" em mensagens de sucesso estão sem acento.
  **SUGESTÃO:** Corrigir para "Vídeo enfileirado", "A geração foi iniciada".
  **SEVERIDADE:** baixa
- **LINHA:** ~218
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Botão de "Gerar Vídeo" não usa `aria-busy` durante loading.
  **SUGESTÃO:** Adicionar `aria-busy={generating}`.
  **SEVERIDADE:** baixa

---

### ARQUIVO: `frontend/src/components/dashboard/PurchaseHistory.tsx`
- **LINHA:** ~11
  **CHECKLIST:** Dark mode / Tailwind
  **PROBLEMA:** Cores de status (`approved`, `pending`, `rejected`) usam hex codes hardcoded.
  **SUGESTÃO:** Usar classes Tailwind (text-green-500, etc) ou variáveis de tema.
  **SEVERIDADE:** baixa
- **LINHA:** ~65
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Tabela de histórico sem `caption` ou `scope` nos headers.
  **SUGESTÃO:** Adicionar `scope="col"` aos `<th>`.
  **SEVERIDADE:** baixa

---

### ARQUIVO: `frontend/src/components/dashboard/StyleSelector.tsx`
- **LINHA:** ~26
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Emojis nos botões não têm `aria-hidden="true"`.
  **SUGESTÃO:** Envolver emojis em `<span aria-hidden="true">`.
  **SEVERIDADE:** baixa
- **LINHA:** ~26
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Botões de seleção não indicam estado via `aria-pressed`.
  **SUGESTÃO:** Adicionar `aria-pressed={selected === s.value}`.
  **SEVERIDADE:** média

---

### ARQUIVO: `frontend/src/components/dashboard/CreditPackageCard.tsx`
- **LINHA:** ~46
  **CHECKLIST:** Dark mode / Tailwind
  **PROBLEMA:** Gradiente hardcoded no badge e botão.
  **SUGESTÃO:** Usar classes Tailwind para consistência com o tema.
  **SEVERIDADE:** baixa
- **LINHA:** ~74
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Botão "Comprar" não usa `aria-busy` durante loading.
  **SUGESTÃO:** Adicionar `aria-busy={loading}`.
  **SEVERIDADE:** baixa

---

### ARQUIVO: `frontend/src/components/dashboard/FilterBar.tsx`
- **LINHA:** ~30
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Botões de filtro não usam `aria-pressed`.
  **SUGESTÃO:** Adicionar `aria-pressed={active}`.
  **SEVERIDADE:** média
- **LINHA:** ~21
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Grupos de filtros não estão agrupados semanticamente.
  **SUGESTÃO:** Usar `role="group"` ou `fieldset` para cada categoria de filtro.
  **SEVERIDADE:** baixa

---

### ARQUIVO: `frontend/src/components/dashboard/ExportCostBanner.tsx`
- **LINHA:** ~13
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Banner de custo não tem role semântico.
  **SUGESTÃO:** Adicionar `role="status"` ou `role="alert"`.
  **SEVERIDADE:** baixa

---

### ARQUIVO: `frontend/src/components/dashboard/KineticTypographyPreview.tsx`
- **LINHA:** ~166
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Canvas não possui descrição acessível.
  **SUGESTÃO:** Adicionar `role="img"` e `aria-label="Preview da animação de texto"`.
  **SEVERIDADE:** média
- **LINHA:** ~174
  **CHECKLIST:** Idioma
  **PROBLEMA:** Botão "Play" está em inglês.
  **SUGESTÃO:** Alterar para "Reproduzir" ou "Iniciar".
  **SEVERIDADE:** baixa

---

### ARQUIVO: `frontend/src/components/dashboard/WpmSlider.tsx`
- **LINHA:** ~22
  **CHECKLIST:** Idioma
  **PROBLEMA:** "rapido" sem acento.
  **SUGESTÃO:** Corrigir para "rápido".
  **SEVERIDADE:** baixa
- **LINHA:** ~15
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Input range não associado ao label.
  **SUGESTÃO:** Adicionar `id` ao input e `htmlFor` ao label.
  **SEVERIDADE:** média

---

### ARQUIVO: `frontend/src/components/dashboard/TemplateSelector.tsx`
- **LINHA:** ~24
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Emojis sem `aria-hidden="true"`.
  **SUGESTÃO:** Adicionar `aria-hidden="true"`.
  **SEVERIDADE:** baixa
- **LINHA:** ~21
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Botões de seleção não indicam estado via `aria-pressed`.
  **SUGESTÃO:** Adicionar `aria-pressed={selected === t.id}`.
  **SEVERIDADE:** média

---

### ARQUIVO: `frontend/src/components/dashboard/EmptyState.tsx`
- **LINHA:** ~4
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Emoji decorativo sem `aria-hidden="true"`.
  **SUGESTÃO:** Adicionar `aria-hidden="true"`.
  **SEVERIDADE:** baixa

---

### ARQUIVO: `frontend/src/components/dashboard/CreditsBadge.tsx`
- **LINHA:** ~11
  **CHECKLIST:** Acessibilidade
  **PROBLEMA:** Badge de créditos não descreve o estado de "créditos esgotados" (vermelho) para leitores de tela.
  **SUGESTÃO:** Adicionar `aria-label={`${credits} créditos disponíveis${isEmpty ? ' - Créditos esgotados' : ''}`}``.
  **SEVERIDADE:** média

---

## Resumo da Auditoria

| Severidade | Quantidade |
| :--- | :--- |
| Alta | 0 |
| Média | 12 |
| Baixa | 18 |
| **Total** | **30** |

**Nota:** A maioria dos problemas está concentrada em **Acessibilidade** (falta de labels associados e estados `aria`) e **Consistência de Tema** (cores hardcoded via `style`). Não foram encontrados erros de funcionalidade ou TypeScript impeditivos.
