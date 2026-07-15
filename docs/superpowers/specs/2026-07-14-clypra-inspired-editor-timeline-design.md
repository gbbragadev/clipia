# Spec — timeline avançada inspirada no Clypra

> Direção aprovada pelo usuário em 2026-07-14: incorporar ao editor ClipIA os padrões úteis do
> Clypra, sem substituir o produto por um editor genérico. Branch:
> `codex/clypra-editor-incorporation`.

## Contexto e decisão

O editor ClipIA é um editor orientado a vídeos narrados: `CompositionData` mantém cenas, palavras
sincronizadas, áudio, mídias, legenda, overlays, voz e música; o preview e o export usam Remotion.
O Clypra é um editor generalista desktop-first, com timeline multifaixa, filmstrips, waveforms,
zoom, drag-and-drop e processamento local via Tauri/Rust/FFmpeg.

A incorporação será seletiva. A ClipIA continuará sendo um SaaS web que produz o primeiro corte e
oferece ajustes simples. Serão reimplementados os padrões de interação que melhoram a leitura e a
manipulação da timeline, sem importar o shell nativo, o motor de exportação ou o modelo de projeto
do Clypra.

Referência avaliada: `AIEraDev/Clypra` no commit
`cc27f9121790801cb659482b6b4ae76618a042b4`, licença MIT.

## Resultado pretendido

- Tornar a timeline atual informativa o suficiente para entender cenas, narração e posição do
  playhead sem abrir vários painéis.
- Permitir reordenar cenas com mouse, teclado ou toque sem perder a correspondência entre cena e
  mídia.
- Preservar o fluxo rápido atual: cinco abas, preview Remotion, autosave, undo/redo e exportação.
- Manter o mobile compacto: a timeline avançada continua dentro da gaveta existente e só decodifica
  áudio quando estiver visível.
- Fazer o estado salvo e o MP4 exportado refletirem a mesma ordem de cenas e mídias.

## Escopo funcional

### 1. Modelo puro da timeline

Criar um módulo pequeno e sem React para:

- calcular os intervalos proporcionais de cada cena;
- limitar o zoom a uma faixa estável;
- mover uma cena de uma posição para outra;
- mover o item correspondente de `mediaUrls` na mesma operação;
- rejeitar índices inválidos e tratar movimentos sem efeito como no-op.

O helper retorna uma nova `CompositionData`; não altera o objeto recebido. `words` e `audioUrl`
permanecem intactos até a regeneração de narração.

### 2. Estado e sincronização

`EditorContext` exporá `reorderScenes(fromIndex, toIndex)`. A operação:

1. usa o helper puro;
2. cria uma única entrada no histórico;
3. seleciona a cena na nova posição;
4. marca `narrationStale=true`, pois a ordem do texto mudou em relação ao áudio atual;
5. dispara o autosave existente.

O aviso e o gate já existentes no `ExportPanel` continuam sendo a proteção contra exportar áudio e
legendas antigos sem confirmação. A regeneração de narração redefine a nova ordem como baseline.
Undo/redo também devem recalcular `narrationStale` considerando texto **e ordem**, não apenas o texto
do mesmo índice.

### 3. Timeline visual enriquecida

Substituir os blocos numerados simples por uma faixa horizontal com:

- toolbar `Diminuir zoom`, `Ajustar`, `Aumentar zoom`;
- régua de tempo com largura proporcional ao zoom;
- card por cena com número, duração e filmstrip da mídia;
- playhead e click-to-seek existentes;
- faixa de narração com waveform real;
- faixa de palavras sincronizadas existente;
- botões acessíveis `Mover cena para trás/frente`;
- drag-and-drop no desktop como atalho adicional, nunca como única forma de reordenar.

O zoom altera apenas a apresentação. Não modifica duração, áudio ou custo. Em `Ajustar`, a timeline
volta a caber na largura disponível.

### 4. Filmstrip compartilhado

Extrair a captura de thumbnail atualmente embutida em `SceneGrid` para um componente/hook
reutilizável. As capturas ficam em cache por URL durante a sessão, são limitadas à resolução visual
necessária e têm fallback neutro quando o canvas não puder ler a mídia.

Não haverá upload, persistência adicional ou geração no backend.

### 5. Waveform da narração

Criar uma faixa que:

- busca `audioUrl` somente quando montada;
- decodifica com Web Audio API;
- reduz os canais a picos RMS limitados pela largura do contêiner;
- mantém cache em memória por URL;
- aborta trabalho ao desmontar;
- mostra fallback discreto e acessível quando a decodificação falhar.

O waveform é informativo; não oferece corte de áudio nesta entrega.

### 6. Desktop e mobile

- Desktop: timeline enriquecida permanece visível no rodapé atual.
- Mobile: continua fechada por padrão na gaveta existente, sem acrescentar controles ao formulário
  principal; ao abrir, toolbar e ações de reordenação usam alvos de pelo menos 44 px.
- Em 320, 390 e 393 px não pode haver overflow no documento. Scroll horizontal é permitido somente
  dentro da faixa da timeline quando o zoom for maior que `Ajustar`.

## Compatibilidade e dados

- Nenhuma migration, variável de ambiente ou novo serviço.
- Nenhum pacote do Clypra em runtime nesta etapa.
- Nenhuma alteração em créditos, autenticação, geração inicial ou APIs públicas.
- `editor_state.json` continua armazenando `composition`; cenas e `mediaUrls` reordenados usam o
  contrato existente.
- Backend e renderer devem continuar aceitando estados antigos sem campos novos.
- A fidelidade `preview == export` é obrigatória.

## Fora de escopo

- Tauri, Rust, FFmpeg local, Capacitor, filesystem local ou formato `.clypra`.
- Timeline multifaixa genérica, ripple edit, split, gaps ou transições do Clypra.
- Trim arbitrário da mídia: os arquivos de cena atuais já chegam recortados; isso exige preservar
  fontes mais longas e seus metadados no backend.
- Troca do `EditorContext` por Zustand.
- Novo motor de efeitos/shaders.
- Deploy, PR ou alteração de preços.

## Tratamento de erros

- Falha de thumbnail: card mantém identificação, duração e fallback visual.
- Falha de waveform: faixa mantém rótulo e estado indisponível sem bloquear edição.
- Falha de autosave: comportamento atual `Falha ao salvar` e retry permanece autoritativo.
- Reordenação durante playback pausa o player antes da mudança e busca o início da cena movida.
- Índices inválidos e drops fora da faixa não mudam o estado.

## Testes e aceite

### Testes primeiro

Começar com Playwright falhando contra uma composição controlada e, para lógica pura, um teste
executável sem browser. Os testes precisam falhar porque a timeline enriquecida ainda não existe.

### Cobertura automatizada

- Reordenação move `scenes` e `mediaUrls` juntas e preserva os demais campos.
- No-op e índices inválidos não criam novo estado.
- Reordenação gera uma única entrada de undo e marca narração desatualizada.
- Undo restaura ordem e correspondência de mídia.
- Zoom respeita limites e `Ajustar` volta à largura base.
- Desktop mostra filmstrips, waveform, régua, playhead e ações acessíveis.
- Mobile abre a gaveta, permite reordenar sem drag e não cria overflow em 320, 390 e 393 px.
- Autosave envia a nova ordem; exportação usa a composição salva.
- Estado antigo continua carregando sem transformação destrutiva.

### Verificações

- testes Playwright focados da timeline;
- `npx.cmd tsc --noEmit`;
- build Next.js em `NEXT_DIST_DIR` isolado;
- testes backend focados de props do Remotion;
- `npm run test:release-b` para regressão pública;
- smoke visual do editor em 390 e 1280 px.

## Avaliação deep após implementação

Executar `startup-user-simulator` em modo `deep`, focado no editor, com cinco personas e evidência
separada por desktop e mobile. O caminho mínimo é:

1. abrir um job editável;
2. reproduzir e buscar na timeline;
3. aumentar/reduzir/ajustar zoom;
4. reordenar cena com botão acessível e, no desktop, por drag;
5. confirmar filmstrip e waveform/fallback;
6. desfazer/refazer;
7. regenerar narração após a mudança de ordem;
8. aplicar legenda e música;
9. salvar, renderizar, baixar e validar o MP4;
10. verificar consumo de créditos e ausência de overflow.

Se a avaliação usar mocks ou não puder concluir geração/render real, isso deve aparecer no veredito
e nos limites; falhas nunca serão substituídas por estimativas. O relatório será salvo em
`outputs/startup-user-simulation-clipia-editor-clypra-incorporation-deep.html`.

## Critério de sucesso

A incorporação é aceita quando um usuário consegue compreender e reordenar as cenas mais rápido,
sem perder a simplicidade do editor, sem dessincronização silenciosa e sem alterar o pipeline de
renderização ou créditos.
