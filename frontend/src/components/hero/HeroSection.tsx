import PretextCanvas from './PretextCanvas'
import PhoneMockup from './PhoneMockup'

export default function HeroSection() {
  return (
    <section className="min-h-screen px-4 pt-20 pb-10">
      <div className="max-w-6xl mx-auto grid md:grid-cols-2 gap-12 items-center min-h-[calc(100vh-5rem)]">
        {/* Mobile: phone on top */}
        <div className="md:hidden flex justify-center">
          <PhoneMockup />
        </div>

        {/* Left column */}
        <div className="flex flex-col items-start">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full border border-purple-500/30 bg-purple-500/10 text-purple-300 text-sm mb-8">
            <span className="w-2 h-2 rounded-full bg-purple-400 animate-pulse" />
            Beta privado
          </div>

          <PretextCanvas />

          <p className="text-xl md:text-2xl text-gray-400 max-w-xl mt-6 mb-8 leading-relaxed">
            Transforme qualquer tema em videos curtos prontos para publicar.
            Roteiro, narracao, legendas e edicao — tudo automatico.
          </p>

          {/* Platform pills */}
          <div className="flex gap-3 mb-8">
            <span className="px-4 py-2 rounded-full border border-red-500/30 bg-red-500/10 text-red-300 text-sm font-medium">
              Shorts
            </span>
            <span className="px-4 py-2 rounded-full border border-pink-500/30 bg-pink-500/10 text-pink-300 text-sm font-medium">
              Reels
            </span>
            <span className="px-4 py-2 rounded-full border border-cyan-500/30 bg-cyan-500/10 text-cyan-300 text-sm font-medium">
              TikTok
            </span>
          </div>

          {/* CTA buttons */}
          <div className="flex gap-4">
            <a href="#demo" className="px-6 py-3 rounded-lg bg-gradient-to-r from-purple-600 to-blue-600 text-white font-medium hover:opacity-90 transition">
              Experimentar agora
            </a>
            <a href="#como-funciona" className="px-6 py-3 rounded-lg border border-gray-700 text-gray-300 hover:border-gray-500 transition">
              Como funciona
            </a>
          </div>
        </div>

        {/* Right column — desktop only */}
        <div className="hidden md:flex justify-center">
          <PhoneMockup />
        </div>
      </div>
    </section>
  )
}
