'use client'

import { useState } from 'react'
import dynamic from 'next/dynamic'
import { useEditor } from '@/contexts/EditorContext'
import { EditorTimeline } from './EditorTimeline'
import { SceneGrid } from './SceneGrid'
import { SubtitleEditor } from './SubtitleEditor'
import { VoiceSelector } from './VoiceSelector'
import { OverlayPicker } from './OverlayPicker'
import { AIAssistant } from './AIAssistant'
import { ExportPanel } from './ExportPanel'
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts'

const VideoPlayer = dynamic(() => import('./VideoPlayer').then((m) => ({ default: m.VideoPlayer })), {
  ssr: false,
  loading: () => (
    <div className="editor-player-container" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="editor-loading__spinner" />
    </div>
  ),
})

const PANELS = [
  { key: 'scenes' as const, label: 'Cenas', icon: '▦' },
  { key: 'voice' as const, label: 'Voz', icon: '♪' },
  { key: 'subtitles' as const, label: 'Legendas', icon: 'T' },
  { key: 'elements' as const, label: 'Elementos', icon: '◈' },
  { key: 'ai' as const, label: 'IA', icon: '✦' },
]

export function EditorLayout() {
  const { loading, error, saving, dirty, activePanel, setActivePanel, panelCollapsed, togglePanel, composition } = useEditor()
  const [showExport, setShowExport] = useState(false)
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
      <div className="editor">
        <div className="editor-loading">
          <div className="editor-loading__title" style={{ color: '#ef4444' }}>Erro ao carregar</div>
          <div className="editor-loading__sub">{error}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="editor">
      {/* Row 1: Header */}
      <header className="editor-header">
        <div className="editor-header__left">
          <a href="/" className="editor-header__logo">ClipIA</a>
          <span className="editor-header__sep">/</span>
          <span className="editor-header__title">{composition?.title || 'Sem titulo'}</span>
        </div>
        <div className="editor-header__right">
          {saving && <span className="editor-header__status editor-header__status--saving">Salvando...</span>}
          {dirty && !saving && <span className="editor-header__status editor-header__status--dirty">Nao salvo</span>}
          {!dirty && !saving && <span className="editor-header__status editor-header__status--saved">Salvo</span>}
          <button className="editor-header__export" onClick={() => setShowExport(true)}>Exportar Video</button>
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
            {activePanel === 'elements' && <OverlayPicker />}
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

      {/* Row 3: Timeline (full width) */}
      <EditorTimeline />

      {showExport && <ExportPanel onClose={() => setShowExport(false)} />}
    </div>
  )
}
