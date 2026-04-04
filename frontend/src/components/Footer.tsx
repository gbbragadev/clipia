export default function Footer() {
  return (
    <footer>
      <div className="filmstrip-border w-full opacity-30" />
      <div className="py-8 px-4">
        <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-sm text-gray-500">
          <span className="bg-gradient-to-r from-purple-400 to-blue-400 bg-clip-text text-transparent font-semibold">
            Auto Shorts
          </span>
          <span className="text-gray-600 text-xs">Feito com IA, para criadores de conteudo</span>
          <span>Powered by IA &middot; {new Date().getFullYear()}</span>
        </div>
      </div>
    </footer>
  )
}
