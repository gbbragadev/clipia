'use client'

import { useEffect, useRef, useState } from 'react'
import { useEditor } from '@/contexts/EditorContext'

interface MusicTrack {
  id: string
  name: string
  mood: string
  url: string
}

const TRACKS: MusicTrack[] = [
  { id: 'lofi-chill', name: 'Lo-Fi Chill', mood: 'Relaxante', url: '/music/lofi-chill.mp3' },
  { id: 'upbeat-energy', name: 'Upbeat Energy', mood: 'Energetico', url: '/music/upbeat-energy.mp3' },
  { id: 'dramatic-epic', name: 'Dramatic Epic', mood: 'Dramatico', url: '/music/dramatic-epic.mp3' },
  { id: 'ambient-calm', name: 'Ambient Calm', mood: 'Tranquilo', url: '/music/ambient-calm.mp3' },
  { id: 'cinematic-tension', name: 'Cinematic Tension', mood: 'Cinematico', url: '/music/cinematic-tension.mp3' },
  { id: 'happy-pop', name: 'Happy Pop', mood: 'Alegre', url: '/music/happy-pop.mp3' },
  { id: 'dark-ambient', name: 'Dark Ambient', mood: 'Sombrio', url: '/music/dark-ambient.mp3' },
  { id: 'inspirational', name: 'Inspirational', mood: 'Motivacional', url: '/music/inspirational.mp3' },
  { id: 'dreamy-space', name: 'Dreamy Space', mood: 'Onirico', url: '/music/dreamy-space.mp3' },
  { id: 'tech-pulse', name: 'Tech Pulse', mood: 'Tecnologico', url: '/music/tech-pulse.mp3' },
]

const MOOD_COLORS: Record<string, string> = {
  Relaxante: 'var(--color-coral)',
  Energetico: '#f59e0b',
  Dramatico: '#ef4444',
  Tranquilo: '#10b981',
  Cinematico: '#3b82f6',
  Alegre: '#f472b6',
  Sombrio: '#6b7280',
  Motivacional: '#8b5cf6',
  Onirico: '#06b6d4',
  Tecnologico: '#22d3ee',
}

export function MusicSelector() {
  const { composition, updateMusic } = useEditor()
  const [previewId, setPreviewId] = useState<string | null>(null)
  const audioRef = useRef<HTMLAudioElement | null>(null)

  const selectedUrl = composition?.musicUrl || null
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

    const audio = new Audio(track.url)
    audio.volume = Math.max(0.3, volume)
    audio.loop = true
    audio.onerror = () => {
      console.error('Failed to load audio:', track.url)
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
    updateMusic(track?.url ?? null)
  }

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const vol = parseInt(e.target.value) / 100
    updateMusic(selectedUrl, vol)
    if (audioRef.current) audioRef.current.volume = vol
  }

  return (
    <div style={{ padding: '0 4px' }}>
      <h4 style={{ color: '#E8E8E8', fontSize: 13, fontWeight: 600, margin: '0 0 12px' }}>
        Musica de Fundo
      </h4>

      <button
        onClick={() => selectTrack(null)}
        style={{
          width: '100%',
          padding: '10px 12px',
          borderRadius: 8,
          border: selectedUrl === null ? '1px solid var(--color-coral)' : '1px solid #333',
          background: selectedUrl === null ? 'rgba(255, 86, 56, 0.15)' : '#2A2A2A',
          color: '#E8E8E8',
          cursor: 'pointer',
          fontSize: 13,
          marginBottom: 8,
          textAlign: 'left',
        }}
      >
        Sem musica
      </button>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        {TRACKS.map((track) => {
          const isSelected = selectedUrl === track.url
          const isPreviewing = previewId === track.id
          const moodColor = MOOD_COLORS[track.mood] || 'var(--color-coral)'

          return (
            <div
              key={track.id}
              onClick={() => selectTrack(track)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                padding: '8px 10px',
                borderRadius: 8,
                border: isSelected ? `1px solid ${moodColor}` : '1px solid #333',
                background: isSelected ? `${moodColor}15` : '#2A2A2A',
                cursor: 'pointer',
              }}
            >
              <button
                onClick={(e) => { e.stopPropagation(); togglePreview(track) }}
                style={{
                  width: 28,
                  height: 28,
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
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ color: '#E8E8E8', fontSize: 13, fontWeight: 500 }}>{track.name}</div>
                <div style={{ color: moodColor, fontSize: 11 }}>{track.mood}</div>
              </div>
              {isSelected && (
                <span style={{ color: moodColor, fontSize: 11, fontWeight: 600 }}>Ativo</span>
              )}
            </div>
          )
        })}
      </div>

      <div style={{ marginTop: 14 }}>
        <label style={{ color: '#aaa', fontSize: 12, display: 'block', marginBottom: 6 }}>
          Volume: {Math.round(volume * 100)}%
        </label>
        <input
          type="range"
          min={0}
          max={100}
          value={Math.round(volume * 100)}
          onChange={handleVolumeChange}
          className="editor-slider"
          style={{ width: '100%' }}
        />
      </div>
    </div>
  )
}
