'use client'

import { strings } from '@/lib/strings';
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
  { key: 'scenes' as const, label: strings.editor.scenes, icon: '▦' },
  { key: 'voice' as const, label: strings.editor.voice, icon: '♪' },
  { key: 'subtitles' as const, label: strings.editor.subtitles, icon: 'T' },
  { key: 'elements' as const, label: strings.editor.elements, icon: '◈' },
  { key: 'ai' as const, label: strings.editor.ai, icon: '✦' },
]

export function EditorLayout() {
  const { loading, error, saving, dirty, activePanel, setActivePanel, panelCollapsed, togglePanel, composition } = useEditor()
  const [showExport, setShowExport] = useState(false)
  const isMobile = useIsMobile()
  const [timelineOpen, setTimelineOpen] = useState(false)
  useKeyboardShortcuts()

  if (loading) {
    return (
      <div className="editor">
        <div className="editor-loading">
          <div className="editor-loading__spinner" />
          <div className="editor-loading__title">Preparando editor</div>
          <div className="editor-loading__sub">Carregando composicao e midias...</div>
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
          {dirty && !saving && <span className="editor-header__status editor-header__status--dirty">Não salvo</span>}
          {!dirty && !saving && <span className="editor-header__status editor-header__status--saved">{strings.editor.saved}</span>}
          <button className="editor-header__export" onClick={() => setShowExport(true)}>Exportar Vídeo</button>
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
                <span className="editor-tab__icon">{p.icon}</span>
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
                <div style={{ borderTop: '1px solid #333', margin: '16px 0' }} />
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
          title="Tab"
        >
          {panelCollapsed ? '◂' : '▸'}
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
            ⏱ Linha do tempo
          </button>
          {timelineOpen && (
            <>
              <div className="editor-timeline-backdrop" onClick={() => setTimelineOpen(false)} />
              <div className="editor-timeline-drawer" role="dialog" aria-label="Linha do tempo">
                <div className="editor-timeline-drawer__handle">
                  <span>Linha do tempo</span>
                  <button className="editor-timeline-drawer__close" onClick={() => setTimelineOpen(false)}>
                    Fechar ✕
                  </button>
                </div>
                <EditorTimeline />
              </div>
            </>
          )}
        </>
      )}

      {showExport && <ExportPanel onClose={() => setShowExport(false)} />}
    </div>
  )
}
