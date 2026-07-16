'use client'

import { useEffect, useRef, useState } from 'react'
import { useEditor } from '@/contexts/EditorContext'
import { musicAssetUrl, type MusicAssetId } from '@/remotion/music-assets'
import { ThrottledRange } from './ThrottledRange'

interface MusicTrack {
  id: MusicAssetId
  name: string
  mood: string
}

const TRACKS: MusicTrack[] = [
  { id: 'lofi-chill', name: 'Lo-Fi Chill', mood: 'Relaxante' },
  { id: 'upbeat-energy', name: 'Upbeat Energy', mood: 'Energético' },
  { id: 'dramatic-epic', name: 'Dramatic Epic', mood: 'Dramático' },
  { id: 'ambient-calm', name: 'Ambient Calm', mood: 'Tranquilo' },
  { id: 'cinematic-tension', name: 'Cinematic Tension', mood: 'Cinemático' },
  { id: 'happy-pop', name: 'Happy Pop', mood: 'Alegre' },
  { id: 'dark-ambient', name: 'Dark Ambient', mood: 'Sombrio' },
  { id: 'inspirational', name: 'Inspirational', mood: 'Motivacional' },
  { id: 'dreamy-space', name: 'Dreamy Space', mood: 'Onírico' },
  { id: 'tech-pulse', name: 'Tech Pulse', mood: 'Tecnológico' },
]

const MOOD_COLORS: Record<string, string> = {
  Relaxante: 'var(--color-coral)',
  Energético: '#f59e0b',
  Dramático: '#ef4444',
  Tranquilo: '#10b981',
  Cinemático: '#3b82f6',
  Alegre: '#f472b6',
  Sombrio: '#6b7280',
  Motivacional: '#fb923c',
  Onírico: '#06b6d4',
  Tecnológico: '#22d3ee',
}

export function MusicSelector() {
  const { composition, updateMusic } = useEditor()
  const [previewId, setPreviewId] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const selectedAssetId = composition?.musicAssetId || null
  const volume = composition?.musicVolume ?? 0.15

  // Cleanup audio on unmount
  useEffect(() => {
    return () => { audioRef.current?.pause() }
  }, [])

  const togglePreview = (track: MusicTrack) => {
    if (previewId === track.id) {
      audioRef.current?.pause()
      setPreviewId(null)
      return
    }
    if (audioRef.current) audioRef.current.pause()

    const trackUrl = musicAssetUrl(track.id)
    if (!trackUrl) return
    const audio = new Audio(trackUrl)
    audio.volume = Math.max(0.3, volume)
    audio.loop = true
    audio.onerror = () => {
      console.error('Failed to load audio:', track.id)
      setPreviewId(null)
    }
    audio.play()
      .then(() => setPreviewId(track.id))
      .catch((err) => {
        console.error('Audio play failed:', err)
        setPreviewId(null)
      })
    audioRef.current = audio
  }

  const selectTrack = (track: MusicTrack | null) => {
    updateMusic(track?.id ?? null)
  }

  // Volume ao vivo no preview de áudio; commit no contexto vem throttled do
  // ThrottledRange (updateMusic por pixel remontava o Player via key=version).
  const applyLiveVolume = (v: number) => {
    if (audioRef.current) audioRef.current.volume = v / 100
  }
  const commitVolume = (v: number) => {
    updateMusic(selectedAssetId, v / 100)
  }

  const handleRadioKeys = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (!['ArrowDown', 'ArrowRight', 'ArrowUp', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return
    const radios = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('[role="radio"]'))
    if (radios.length === 0) return
    const currentIndex = Math.max(0, radios.indexOf(document.activeElement as HTMLElement))
    const targetIndex = event.key === 'Home'
      ? 0
      : event.key === 'End'
        ? radios.length - 1
        : event.key === 'ArrowDown' || event.key === 'ArrowRight'
          ? (currentIndex + 1) % radios.length
          : (currentIndex - 1 + radios.length) % radios.length
    event.preventDefault()
    radios[targetIndex].focus()
    radios[targetIndex].click()
  }

  return (
    <div style={{ padding: '0 4px' }}>
      <h4 style={{ color: '#E8E8E8', fontSize: 13, fontWeight: 600, margin: '0 0 12px' }}>
        Música de fundo
      </h4>

      <div
        role="radiogroup"
        aria-label="Trilha sonora"
        onKeyDown={handleRadioKeys}
        style={{ display: 'flex', flexDirection: 'column', gap: 6 }}
      >
        <button
          type="button"
          role="radio"
          aria-checked={selectedAssetId === null}
          tabIndex={selectedAssetId === null ? 0 : -1}
          onClick={() => selectTrack(null)}
          style={{
            width: '100%',
            padding: '10px 12px',
            borderRadius: 8,
            border: selectedAssetId === null ? '1px solid var(--color-coral)' : '1px solid #333',
            background: selectedAssetId === null ? 'rgba(255, 86, 56, 0.15)' : '#2A2A2A',
            color: '#E8E8E8',
            cursor: 'pointer',
            fontSize: 13,
            textAlign: 'left',
          }}
        >
          Sem música
        </button>

        {TRACKS.map((track) => {
          const isSelected = selectedAssetId === track.id
          const isPreviewing = previewId === track.id
          const moodColor = MOOD_COLORS[track.mood] || 'var(--color-coral)'

          return (
            <div
              key={track.id}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 4,
                padding: 4,
                borderRadius: 8,
                border: isSelected ? `1px solid ${moodColor}` : '1px solid #333',
                background: isSelected ? `${moodColor}15` : '#2A2A2A',
              }}
            >
              <button
                type="button"
                role="radio"
                aria-checked={isSelected}
                tabIndex={isSelected ? 0 : -1}
                aria-label={`${track.name} — ${track.mood}`}
                onClick={() => selectTrack(track)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  flex: 1,
                  minWidth: 0,
                  minHeight: 36,
                  padding: '4px 6px',
                  border: 'none',
                  background: 'transparent',
                  color: '#E8E8E8',
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <span aria-hidden="true" style={{ color: moodColor, fontSize: 14 }}>
                  {isSelected ? '●' : '○'}
                </span>
                <span style={{ flex: 1, minWidth: 0 }}>
                  <span style={{ display: 'block', fontSize: 13, fontWeight: 500 }}>{track.name}</span>
                  <span style={{ display: 'block', color: moodColor, fontSize: 11 }}>{track.mood}</span>
                </span>
                {isSelected && (
                  <span style={{ color: moodColor, fontSize: 11, fontWeight: 600 }}>Ativo</span>
                )}
              </button>
              <button
                type="button"
                aria-label={isPreviewing ? `Pausar prévia de ${track.name}` : `Ouvir prévia de ${track.name}`}
                onClick={() => togglePreview(track)}
                style={{
                  width: 36,
                  height: 36,
                  borderRadius: '50%',
                  border: 'none',
                  background: isPreviewing ? moodColor : '#444',
                  color: '#fff',
                  cursor: 'pointer',
                  fontSize: 11,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  flexShrink: 0,
                }}
              >
                {isPreviewing ? '⏸' : '▶'}
              </button>
            </div>
          )
        })}
      </div>

      <div style={{ marginTop: 14 }}>
        <label style={{ color: '#aaa', fontSize: 12, display: 'block', marginBottom: 6 }}>
          Volume: {Math.round(volume * 100)}%
        </label>
        <ThrottledRange
          min={0}
          max={100}
          value={Math.round(volume * 100)}
          onCommit={commitVolume}
          onLive={applyLiveVolume}
        />
      </div>
    </div>
  )
}
