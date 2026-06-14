'use client'

interface Props {
  downloadUrl: string
}

export default function VideoPlayer({ downloadUrl }: Props) {
  return (
    <div className="mt-6 space-y-4">
      {/* Phone frame wrapper */}
      <div className="w-full max-w-[280px] mx-auto rounded-[2rem] border-4 border-gray-700/50 bg-black overflow-hidden shadow-2xl shadow-purple-500/10">
        <video
          src={downloadUrl}
          controls
          autoPlay
          className="w-full"
          style={{ aspectRatio: '9/16' }}
        />
      </div>
      <div className="text-center">
        <a
          href={downloadUrl}
          download
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg border border-gray-700 text-gray-300 hover:border-purple-500 transition text-sm"
        >
          Baixar video
        </a>
      </div>
    </div>
  )
}
