'use client'

import { useState, useRef, useEffect } from 'react'
import ReelSubtitleCanvas from './ReelSubtitleCanvas'
import { loadShowcase } from '@/lib/showcase'

const PHONE_HEIGHT = 497

interface ReelData {
  title: string
  video: string
  accent: string
  words: string[]
}

function Reel({ reel, isActive, index, muted }: { reel: ReelData; isActive: boolean; index: number; muted: boolean }) {
  const [wordIdx, setWordIdx] = useState(0)
  const videoRef = useRef<HTMLVideoElement>(null)

  useEffect(() => {
    if (!isActive) { setWordIdx(0); return }
    let i = 0
    const id = setInterval(() => {
      i++
      setWordIdx(i)
      if (i > reel.words.length) clearInterval(id)
    }, 250)
    return () => clearInterval(id)
  }, [isActive, reel.words.length])

  useEffect(() => {
    const v = videoRef.current
    if (!v) return
    if (isActive) {
      v.currentTime = 0
      v.play().catch(() => {})
    } else {
      v.pause()
    }
  }, [isActive])

  return (
    <div style={{
      width: '100%', height: PHONE_HEIGHT, flexShrink: 0, scrollSnapAlign: 'start',
      position: 'relative', overflow: 'hidden', background: '#000',
    }}>
      {/* Real Pexels video background */}
      <video
        ref={videoRef}
        src={reel.video}
        muted={muted}
        loop
        playsInline
        style={{
          position: 'absolute', inset: 0,
          width: '100%', height: '100%',
          objectFit: 'cover',
        }}
      />

      {/* Dark overlay for text readability */}
      <div style={{
        position: 'absolute', inset: 0,
        background: 'linear-gradient(180deg, rgba(0,0,0,0.3) 0%, rgba(0,0,0,0.1) 40%, rgba(0,0,0,0.6) 100%)',
      }} />

      {/* Title */}
      <div style={{
        position: 'absolute', top: '25%', left: 0, right: 0,
        textAlign: 'center', padding: '0 28px', zIndex: 2,
      }}>
        <div style={{
          fontSize: 30, fontWeight: 800, color: 'white', lineHeight: 1.15,
          whiteSpace: 'pre-line',
          textShadow: '0 2px 30px rgba(0,0,0,0.7), 0 0 10px rgba(0,0,0,0.5)',
          transform: isActive ? 'scale(1) translateY(0)' : 'scale(0.9) translateY(10px)',
          opacity: isActive ? 1 : 0.5,
          transition: 'all 0.5s ease',
        }}>
          {reel.title}
        </div>
      </div>

      {/* Animated word-by-word subtitle (Pretext canvas) */}
      <ReelSubtitleCanvas
        words={reel.words}
        activeWordIndex={wordIdx - 1}
        accent={reel.accent}
      />

      {/* Social icons removed (no fake metrics) */}

      {/* Author bar */}
      <div style={{
        position: 'absolute', bottom: 18, left: 14,
        display: 'flex', alignItems: 'center', gap: 8, zIndex: 2,
      }}>
        <div style={{
          width: 28, height: 28, borderRadius: '50%',
          background: `linear-gradient(135deg, ${reel.accent}, ${reel.accent}88)`,
          border: '2px solid rgba(255,255,255,0.4)',
        }} />
        <span style={{ fontSize: 12, color: 'rgba(255,255,255,0.9)', fontWeight: 600, textShadow: '0 1px 4px rgba(0,0,0,0.5)' }}>@clipia</span>
        <span style={{
          fontSize: 10, padding: '3px 10px', borderRadius: 4,
          background: reel.accent, color: '#000', fontWeight: 700,
        }}>Seguir</span>
      </div>

    </div>
  )
}

export default function VideoShowcase() {
  const [reels, setReels] = useState<ReelData[]>([])
  const [activeIdx, setActiveIdx] = useState(0)
  const [muted, setMuted] = useState(true)
  const scrollRef = useRef<HTMLDivElement>(null)
  const userScrolled = useRef(false)

  useEffect(() => {
    loadShowcase()
      .then((m) =>
        setReels(
          m.videos
            .filter((v) => v.hero)
            .slice(0, 3)
            .map((v) => ({
              title: v.title,
              video: v.video,
              accent: v.captionAccent,
              words: v.phrase.split(/\s+/),
            }))
        )
      )
      .catch(() => {})
  }, [])

  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    const onScroll = () => {
      userScrolled.current = true
      const idx = Math.round(el.scrollTop / PHONE_HEIGHT)
      setActiveIdx(Math.min(idx, reels.length - 1))
    }
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => el.removeEventListener('scroll', onScroll)
  }, [reels.length])

  useEffect(() => {
    if (reels.length === 0) return
    const id = setInterval(() => {
      if (userScrolled.current) { userScrolled.current = false; return }
      const el = scrollRef.current
      if (!el) return
      const next = (activeIdx + 1) % reels.length
      el.scrollTo({ top: next * PHONE_HEIGHT, behavior: 'smooth' })
    }, 5500)
    return () => clearInterval(id)
  }, [activeIdx, reels.length])

  // Early-return SO depois de todos os hooks (Rules of Hooks — React #310)
  if (reels.length === 0) return null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', position: 'relative' }}>
      <div style={{
        width: 280, height: PHONE_HEIGHT, borderRadius: '2.5rem',
        border: '4px solid rgba(255,255,255,0.12)',
        overflow: 'hidden', position: 'relative',
        boxShadow: `0 0 100px ${reels[activeIdx].accent}30, 0 30px 60px rgba(0,0,0,0.5)`,
        transition: 'box-shadow 0.6s', background: '#000',
      }}>
        {/* Notch */}
        <div style={{
          position: 'absolute', top: 8, left: '50%', transform: 'translateX(-50%)',
          width: 80, height: 24, borderRadius: 12, background: 'rgba(0,0,0,0.7)', zIndex: 20,
        }} />

        {/* Scrollable video feed */}
        <div ref={scrollRef} style={{
          height: '100%', overflowY: 'auto', scrollSnapType: 'y mandatory',
          WebkitOverflowScrolling: 'touch', msOverflowStyle: 'none', scrollbarWidth: 'none',
        }}>
          {reels.map((reel, i) => (
            <Reel key={i} reel={reel} isActive={i === activeIdx} index={i} muted={muted} />
          ))}
        </div>

        {/* Sound toggle button */}
        <button
          type="button"
          onClick={() => setMuted(m => !m)}
          style={{
            position: 'absolute', bottom: 70, right: 14, zIndex: 30,
            width: 32, height: 32, borderRadius: '50%',
            background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(8px)',
            border: '1px solid rgba(255,255,255,0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', color: 'white', fontSize: 14,
            transition: 'all 0.2s',
          }}
          aria-label={muted ? 'Ativar som' : 'Desativar som'}
        >
          {muted ? '\uD83D\uDD07' : '\uD83D\uDD0A'}
        </button>

        {/* Scroll hint on first reel */}
        {activeIdx === 0 && (
          <div style={{
            position: 'absolute', bottom: 60, left: '50%', transform: 'translateX(-50%)',
            animation: 'float 2s ease-in-out infinite', zIndex: 10, pointerEvents: 'none', opacity: 0.4,
          }}>
            <div style={{ width: 16, height: 16, borderBottom: '2px solid white', borderRight: '2px solid white', transform: 'rotate(45deg)' }} />
          </div>
        )}
      </div>

      {/* Dots */}
      <div style={{ display: 'flex', gap: 6, marginTop: 16 }}>
        {reels.map((reel, i) => (
          <div key={i} style={{
            width: i === activeIdx ? 24 : 6, height: 6, borderRadius: 3,
            background: i === activeIdx ? reel.accent : 'rgba(255,255,255,0.15)',
            transition: 'all 0.3s',
          }} />
        ))}
      </div>

      {/* Glow */}
      <div style={{
        position: 'absolute', top: -100, right: -100, width: 320, height: 320,
        borderRadius: '50%', background: `${reels[activeIdx].accent}12`, filter: 'blur(120px)',
        pointerEvents: 'none', transition: 'background 0.6s',
      }} />
    </div>
  )
}
