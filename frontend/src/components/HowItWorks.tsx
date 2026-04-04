'use client'

import { useEffect, useRef, useState } from 'react'
import HowItWorksStepCanvas from './HowItWorksStepCanvas'

const steps = [
  {
    number: '01',
    title: 'Escolha o tema',
    description: 'Digite qualquer assunto e a IA gera um roteiro envolvente em pt-BR.',
    gradient: 'linear-gradient(135deg, #7c3aed, #3b82f6)',
    icon: 'edit',
  },
  {
    number: '02',
    title: 'IA cria o video',
    description: 'Narracao com voz natural, legendas sincronizadas e midia selecionada automaticamente.',
    gradient: 'linear-gradient(135deg, #d946ef, #7c3aed)',
    icon: 'play',
  },
  {
    number: '03',
    title: 'Publique',
    description: 'Baixe em 9:16 e publique direto no YouTube Shorts, Reels ou TikTok.',
    gradient: 'linear-gradient(135deg, #22d3ee, #3b82f6)',
    icon: 'upload',
  },
]

function StepIcon({ type }: { type: string }) {
  const size = 32
  if (type === 'edit') {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7" />
        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z" />
      </svg>
    )
  }
  if (type === 'play') {
    return (
      <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <polygon points="5 3 19 12 5 21 5 3" fill="rgba(255,255,255,0.3)" />
      </svg>
    )
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  )
}

export default function HowItWorks() {
  const [visible, setVisible] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(([e]) => { if (e.isIntersecting) setVisible(true) }, { threshold: 0.1 })
    obs.observe(el)
    return () => obs.disconnect()
  }, [])

  return (
    <section id="como-funciona" style={{ padding: '80px 16px' }} ref={ref}>
      <div style={{ maxWidth: 1000, margin: '0 auto' }}>
        <p style={{ textAlign: 'center', fontSize: 13, fontWeight: 500, color: '#7c3aed', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 8 }}>
          Como funciona
        </p>
        <h2 style={{ textAlign: 'center', fontSize: 'clamp(1.8rem, 3vw, 2.5rem)', fontWeight: 800, color: 'white', marginBottom: 56 }}>
          Do tema ao video em 3 passos
        </h2>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: 24 }}>
          {steps.map((step, i) => (
            <div
              key={step.number}
              style={{
                borderRadius: 20,
                overflow: 'hidden',
                opacity: 1,
              }}
            >
              {/* Gradient header with icon */}
              <div style={{
                background: step.gradient,
                padding: '40px 28px 32px',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                gap: 16,
                position: 'relative',
              }}>
                <div style={{
                  width: 64,
                  height: 64,
                  borderRadius: 16,
                  background: 'rgba(255,255,255,0.15)',
                  backdropFilter: 'blur(8px)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                  <StepIcon type={step.icon} />
                </div>
                <div style={{ position: 'absolute', top: 12, right: 20 }}>
                  <HowItWorksStepCanvas number={step.number} />
                </div>
              </div>

              {/* Text content */}
              <div style={{
                background: 'rgba(255,255,255,0.03)',
                border: '1px solid rgba(255,255,255,0.06)',
                borderTop: 'none',
                padding: '24px 28px 32px',
                borderRadius: '0 0 20px 20px',
              }}>
                <h3 style={{ fontSize: 20, fontWeight: 700, color: 'white', marginBottom: 8 }}>
                  {step.title}
                </h3>
                <p style={{ fontSize: 14, lineHeight: 1.7, color: '#94a3b8' }}>
                  {step.description}
                </p>
              </div>
            </div>
          ))}
        </div>

      </div>
    </section>
  )
}
