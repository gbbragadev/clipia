'use client'

import { Layers, Mic, Captions, Shapes, Sparkles, Clock, X, Download, ChevronLeft, ChevronRight, Undo2, Redo2 } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { strings } from '@/lib/strings';
import { EASE, DURATIONS, useReducedMotionState } from '@/lib/motion'
import { useState } from 'react'
import dynamic from 'next/dynamic'
import { useEditor } from '@/contexts/EditorContext'
import Logo from '@/components/brand/Logo'
import { EditorTimeline } from './EditorTimeline'
import { SceneGrid } from './SceneGrid'
import { SubtitleEditor } from './SubtitleEditor'
import { VoiceSelector } from './VoiceSelector'
import { OverlayPicker } from './OverlayPicker'
import { MusicSelector } from './MusicSelector'
import { AIAssistant } from './AIAssistant'
import { ExportPanel } from './ExportPanel'
import { ResetEditorButton } from './ResetEditorButton'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'
import { useIsMobile } from '@/hooks/useIsMobile'
import { InlineError } from '@/components/ui/feedback'

const VideoPlayer = dynamic(() => import('./VideoPlayer').then((m) => ({ default: m.VideoPlayer })), {
  ssr: false,
  loading: () => (
    <div className="editor-player-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="editor-loading__spinner" />
    </div>
  ),
})

const PANELS = [
  { key: 'scenes' as const, label: strings.editor.scenes, Icon: Layers },
  { key: 'voice' as const, label: strings.editor.voice, Icon: Mic },
  { key: 'subtitles' as const, label: strings.editor.subtitles, Icon: Captions },
  { key: 'elements' as const, label: strings.editor.elements, Icon: Shapes },
  { key: 'ai' as const, label: strings.editor.ai, Icon: Sparkles },
]

export function EditorLayout() {
  const { loading, error, saving, dirty, saveError, retrySave, activePanel, setActivePanel, panelCollapsed, togglePanel, composition, jobId, undo, redo, canUndo, canRedo } = useEditor()
  const [showExport, setShowExport] = useState(false)
  const isMobile = useIsMobile()
  const [timelineOpen, setTimelineOpen] = useState(false)
  const reduceMotion = useReducedMotionState()
  useKeyboardShortcuts()

  if (loading) {
    return (
      <div className="editor">
        <div className="editor-loading">
          <div className="editor-loading__spinner" />
          <div className="editor-loading__title">Preparando editor</div>
          <div className="editor-loading__sub">Carregando composição e mídias...</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="editor" style={{ padding: 24 }}>
        <InlineError
          title="Não foi possível carregar o editor"
          description={error}
          onRetry={() => window.location.reload()}
        />
      </div>
    )
  }

  return (
    <div className="editor">
      {/* Row 1: Header */}
      <header className="editor-header">
        <div className="editor-header__left">
          <a href="/dashboard" className="editor-header__logo"><Logo size="sm" /></a>
          <span className="editor-header__sep">/</span>
          <span className="editor-header__title">{composition?.title || 'Sem titulo'}</span>
        </div>
        <div className="editor-header__right">
          {saving && <span className="editor-header__status editor-header__status--saving">{strings.editor.saving}</span>}
          {saveError && !saving && (
            <button
              type="button"
              onClick={retrySave}
              className="editor-header__status"
              title="As últimas edições não foram salvas no servidor. Clique para tentar de novo."
              style={{
                color: 'var(--color-danger)', background: 'rgba(248,113,113,0.1)',
                border: '1px solid rgba(248,113,113,0.3)', borderRadius: 6, cursor: 'pointer',
              }}
            >
              Falha ao salvar · tentar de novo
            </button>
          )}
          {dirty && !saving && !saveError && <span className="editor-header__status editor-header__status--dirty">Não salvo</span>}
          {!dirty && !saving && !saveError && <span className="editor-header__status editor-header__status--saved">{strings.editor.saved}</span>}
          {isMobile && (
            <>
              {/* Sem teclado não há Ctrl+Z: undo/redo precisam de botão no mobile */}
              <button className="editor-header__icon-btn" onClick={undo} disabled={!canUndo} aria-label="Desfazer">
                <Undo2 className="w-4 h-4" />
              </button>
              <button className="editor-header__icon-btn" onClick={redo} disabled={!canRedo} aria-label="Refazer">
                <Redo2 className="w-4 h-4" />
              </button>
            </>
          )}
          <ResetEditorButton jobId={jobId} />
          <button className="editor-header__export inline-flex items-center gap-1.5" onClick={() => setShowExport(true)}><Download className="w-3.5 h-3.5" /> Exportar</button>
        </div>
      </header>

      {/* Row 2: Workspace (player + tools panel) */}
      <div className="editor-workspace">
        <div className="editor-player-zone">
          <VideoPlayer />
        </div>

        {/* Tools panel */}
        <div className={`editor-tools-panel ${panelCollapsed ? 'editor-tools-panel--collapsed' : ''}`}>
          <nav className="editor-tabs">
            {PANELS.map((p) => (
              <button
                key={p.key}
                onClick={() => setActivePanel(p.key)}
                className={`editor-tab ${activePanel === p.key ? 'editor-tab--active' : ''}`}
              >
                <span className="editor-tab__icon"><p.Icon className="w-4 h-4" /></span>
                <span className="editor-tab__label">{p.label}</span>
              </button>
            ))}
          </nav>
          <div className="editor-panel-content">
            {activePanel === 'scenes' && <SceneGrid />}
            {activePanel === 'voice' && <VoiceSelector />}
            {activePanel === 'subtitles' && <SubtitleEditor />}
            {activePanel === 'elements' && (
              <>
                <OverlayPicker />
                <div style={{ borderTop: '1px solid var(--border-default)', margin: '16px 0' }} />
                <MusicSelector />
              </>
            )}
            {activePanel === 'ai' && <AIAssistant />}
          </div>
        </div>

        {/* Panel toggle */}
        <button
          className={`editor-panel-toggle ${panelCollapsed ? 'editor-panel-toggle--collapsed' : ''}`}
          onClick={togglePanel}
          title={panelCollapsed ? 'Expandir painel' : 'Recolher painel'}
          aria-label={panelCollapsed ? 'Expandir painel' : 'Recolher painel'}
        >
          {panelCollapsed ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>
      </div>

      {/* Row 3: Timeline — inline no desktop, gaveta no mobile */}
      {!isMobile && <EditorTimeline />}
      {isMobile && (
        <>
          <button
            className="editor-timeline-fab"
            onClick={() => setTimelineOpen(true)}
            aria-label="Abrir linha do tempo"
          >
            <Clock className="w-4 h-4" /> Linha do tempo
          </button>
          <AnimatePresence>
            {timelineOpen && (
              <>
                <motion.div
                  className="editor-timeline-backdrop"
                  onClick={() => setTimelineOpen(false)}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: DURATIONS.normal, ease: EASE }}
                />
                <motion.div
                  className="editor-timeline-drawer"
                  role="dialog"
                  aria-label="Linha do tempo"
                  initial={reduceMotion ? false : { y: '100%' }}
                  animate={{ y: 0 }}
                  exit={reduceMotion ? { opacity: 0 } : { y: '100%' }}
                  transition={{ duration: DURATIONS.normal, ease: EASE }}
                >
                  <div className="editor-timeline-drawer__handle">
                    <span>Linha do tempo</span>
                    <button className="editor-timeline-drawer__close" onClick={() => setTimelineOpen(false)}>
                      Fechar <X className="w-4 h-4 inline" />
                    </button>
                  </div>
                  <EditorTimeline />
                </motion.div>
              </>
            )}
          </AnimatePresence>
        </>
      )}

      <AnimatePresence>
        {showExport && <ExportPanel onClose={() => setShowExport(false)} />}
      </AnimatePresence>
    </div>
  )
}
