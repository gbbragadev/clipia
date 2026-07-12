import { strings } from '@/lib/strings';
import Link from 'next/link'
import { FilmstripBackground } from './ui/FilmstripBackground'
import { NICHES } from '@/lib/niches'

export default function Footer() {
  return (
    <footer className="relative bg-[#0b0d15] border-t border-white/5 overflow-hidden">
      <FilmstripBackground speed={30} opacity={0.05} />
      <div className="py-16 px-4 relative z-10">
        <div className="max-w-7xl mx-auto grid grid-cols-1 md:grid-cols-5 gap-8 sm:gap-10 md:gap-12 text-sm text-slate-500">
          <div className="md:col-span-2 space-y-4">
            <span className="text-xl font-bold text-white tracking-tight">
              Clip<span className="text-coral">{strings.editor.ai}</span>
            </span>
            <p className="text-slate-400 max-w-sm leading-relaxed text-base">
              Transforme ideias em vídeos incríveis e profissionais em minutos com o poder da Inteligência Artificial.
            </p>
          </div>
          
          <div className="space-y-4">
            <h4 className="text-white font-semibold mb-4 uppercase tracking-wider text-xs">Produto</h4>
            <ul className="space-y-3">
              <li><Link href="/exemplos" className="hover:text-coral transition">Exemplos</Link></li>
              <li><Link href="/blog" className="hover:text-coral transition">Blog</Link></li>
              <li><Link href="/#demo" className="hover:text-coral transition">Como Funciona</Link></li>
              {process.env.NEXT_PUBLIC_PUBLIC_SIGNUP === "true" && (
                <li><Link href="/auth/register" className="hover:text-coral transition">Criar Conta</Link></li>
              )}
            </ul>
          </div>

          <div className="space-y-4">
            <h4 className="text-white font-semibold mb-4 uppercase tracking-wider text-xs">Nichos</h4>
            <ul className="space-y-3">
              {NICHES.map((n) => (
                <li key={n.slug}>
                  <Link href={`/criar/${n.slug}`} className="hover:text-coral transition">{n.label}</Link>
                </li>
              ))}
            </ul>
          </div>

          <div className="space-y-4">
            <h4 className="text-white font-semibold mb-4 uppercase tracking-wider text-xs">Legal</h4>
            <ul className="space-y-3">
              <li><Link href="/termos" className="hover:text-coral transition">Termos de Uso</Link></li>
              <li><Link href="/privacidade" className="hover:text-coral transition">Privacidade</Link></li>
              <li><span className="text-slate-600">&copy; {new Date().getFullYear()} ClipIA</span></li>
            </ul>
          </div>
        </div>
      </div>
    </footer>
  )
}
