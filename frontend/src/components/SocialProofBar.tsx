export default function SocialProofBar() {
  return (
    <div className="py-8 px-4">
      <div className="max-w-3xl mx-auto flex items-center justify-center gap-6 md:gap-12">
        <div className="text-center">
          <span className="block text-2xl md:text-3xl font-bold font-mono tabular-nums bg-gradient-to-r from-purple-400 to-fuchsia-400 bg-clip-text text-transparent">
            1M+
          </span>
          <span className="text-xs md:text-sm text-gray-500 mt-1 block">views geradas</span>
        </div>

        <div className="w-px h-10 bg-gray-700/50" />

        <div className="text-center">
          <span className="block text-2xl md:text-3xl font-bold font-mono tabular-nums bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
            500+
          </span>
          <span className="text-xs md:text-sm text-gray-500 mt-1 block">videos criados</span>
        </div>

        <div className="w-px h-10 bg-gray-700/50" />

        <div className="text-center">
          <span className="block text-2xl md:text-3xl font-bold font-mono tabular-nums bg-gradient-to-r from-cyan-400 to-green-400 bg-clip-text text-transparent">
            45s
          </span>
          <span className="text-xs md:text-sm text-gray-500 mt-1 block">tempo medio</span>
        </div>
      </div>
    </div>
  )
}
