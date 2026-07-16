export interface RenderRevisionState {
  editRevision: number
  renderedRevision: number
  renderingRevision: number | null
  renderedAt: string | null
}

function isRevision(value: unknown): value is number {
  return Number.isSafeInteger(value) && Number(value) >= 0
}

export function normalizeRenderRevision(
  saved: Partial<RenderRevisionState> | undefined,
  hasSavedEditorState: boolean,
): RenderRevisionState {
  const fallbackRevision = hasSavedEditorState ? 1 : 0
  const editRevision = saved?.editRevision
  const renderedRevision = saved?.renderedRevision
  const renderingRevision = saved?.renderingRevision
  const hasValidContract = isRevision(editRevision)
    && isRevision(renderedRevision)
    && renderedRevision <= editRevision
    && (
      renderingRevision === null
      || (
        isRevision(renderingRevision)
        && renderingRevision >= renderedRevision
        && renderingRevision <= editRevision
      )
    )

  if (!hasValidContract) {
    return {
      editRevision: fallbackRevision,
      renderedRevision: 0,
      renderingRevision: null,
      renderedAt: null,
    }
  }

  return {
    editRevision,
    renderedRevision,
    renderingRevision,
    renderedAt: typeof saved?.renderedAt === 'string' && saved.renderedAt
      ? saved.renderedAt
      : null,
  }
}

export function hasUnrenderedChanges(state: RenderRevisionState): boolean {
  return state.editRevision !== state.renderedRevision
}

export function nextEditRevision<T extends RenderRevisionState>(state: T): T {
  return { ...state, editRevision: state.editRevision + 1 }
}

export function beginRenderRevision<T extends RenderRevisionState>(state: T): T {
  return { ...state, renderingRevision: state.editRevision }
}

export function completeRenderRevision<T extends RenderRevisionState>(
  state: T,
  renderedAt: string,
): T {
  return {
    ...state,
    renderedRevision: state.renderingRevision ?? state.editRevision,
    renderingRevision: null,
    renderedAt,
  }
}
