import VideoShowcase from './VideoShowcase'
import PretextCanvas from './PretextCanvas'

export default function HeroSection() {
  return (
    <section className="hero-bg" style={{ minHeight: '90vh', padding: '100px 16px 40px' }}>
      <div style={{ maxWidth: 1200, margin: '0 auto' }}>
        {/* Desktop: 2-column grid */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 48, alignItems: 'center' }}>
          {/* Left: copy */}
          <div style={{ order: 2 }}>
            <div style={{
              display: 'inline-flex', alignItems: 'center', gap: 8,
              padding: '6px 16px', borderRadius: 20,
              border: '1px solid rgba(139,92,246,0.3)', background: 'rgba(139,92,246,0.08)',
              color: '#c4b5fd', fontSize: 13, marginBottom: 32,
            }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#a78bfa', animation: 'pulse-glow 2s infinite' }} />
              Beta privado
            </div>

            <h1 style={{
              fontSize: 'clamp(2.5rem, 5vw, 4.5rem)', fontWeight: 900,
              color: 'white', lineHeight: 1.05, letterSpacing: '-0.03em', marginBottom: 20,
            }}>
              Crie videos curtos
              <br />
              <span style={{ color: '#a78bfa' }}>com IA</span>
            </h1>

            <p style={{ fontSize: 18, lineHeight: 1.7, color: '#94a3b8', maxWidth: 440, marginBottom: 24 }}>
              Digite um tema e receba um video pronto para publicar.
              Roteiro, narracao, legendas e edicao — tudo automatico em minutos.
            </p>

            {/* Pretext live subtitle preview */}
            <div style={{ width: '100%', maxWidth: 420, marginBottom: 24 }}>
              <PretextCanvas />
            </div>

            {/* Platform pills */}
            <div style={{ display: 'flex', gap: 10, marginBottom: 28, flexWrap: 'wrap' }}>
              {[
                { name: 'YouTube Shorts', color: '#ef4444' },
                { name: 'Reels', color: '#ec4899' },
                { name: 'TikTok', color: '#22d3ee' },
              ].map(p => (
                <span key={p.name} style={{
                  padding: '6px 14px', borderRadius: 20, fontSize: 12, fontWeight: 500,
                  border: `1px solid ${p.color}30`, background: `${p.color}10`, color: `${p.color}cc`,
                }}>
                  {p.name}
                </span>
              ))}
            </div>

            {/* CTAs */}
            <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
              <a href="#demo" className="btn-primary">Experimentar agora</a>
              <a href="#como-funciona" className="btn-outline">Como funciona</a>
            </div>
          </div>

          {/* Right: video showcase — single instance */}
          <div style={{ display: 'flex', justifyContent: 'center', order: 1 }}>
            <VideoShowcase />
          </div>
        </div>
      </div>
    </section>
  )
}
