import { Sparkles } from 'lucide-react'

/**
 * Empty state da grid de vídeos: ilustração leve (três "shorts" fantasmas) +
 * CTA que rola até o formulário de geração (#studio em dashboard/page.tsx).
 */
export default function EmptyState() {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-white/10 bg-white/[0.02] px-6 py-16 text-center">
      {/* Ilustração: 3 cartões 9:16 em leque, cores da marca */}
      <div className="mb-6 flex items-end gap-2" aria-hidden="true">
        <div className="h-20 w-12 -rotate-6 rounded-lg border border-white/10 bg-gradient-to-br from-azure/25 to-transparent" />
        <div className="relative h-24 w-14 rounded-lg border border-coral/30 bg-gradient-to-br from-coral/30 to-azure/20 shadow-lg shadow-coral/10">
          <div className="absolute inset-x-2 bottom-2 space-y-1">
            <div className="h-1 rounded-full bg-white/40" />
            <div className="h-1 w-2/3 rounded-full bg-white/25" />
          </div>
        </div>
        <div className="h-20 w-12 rotate-6 rounded-lg border border-white/10 bg-gradient-to-br from-coral/15 to-transparent" />
      </div>

      <p className="text-lg font-bold text-white">Seus vídeos vão aparecer aqui</p>
      <p className="mt-1 max-w-xs text-sm text-slate-400">
        Escolha um tema, aperte gerar e acompanhe cada etapa até seu primeiro Short ficar pronto para baixar.
      </p>

      <a
        href="#studio"
        className="mt-6 inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-coral to-azure px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 active:scale-[0.98]"
      >
        <Sparkles size={15} />
        Criar meu primeiro vídeo
      </a>
    </div>
  )
}
