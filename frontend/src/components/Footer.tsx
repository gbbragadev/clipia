export default function Footer() {
  return (
    <footer>
      <div className="filmstrip-border w-full opacity-30" />
      <div className="py-8 px-4">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-gray-500">
          <span className="font-semibold">
            Clip<span className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent">IA</span>
          </span>
          <span className="text-gray-600 text-xs">Transforme temas em videos com IA</span>
          <span>ClipIA &middot; {new Date().getFullYear()}</span>
        </div>
      </div>
    </footer>
  )
}
