import { Container } from "@/components/landing/ui/Container";
import { Icon } from "@/components/landing/icons";
import { Reveal } from "@/components/landing/Reveal";

const AUTOMATED_STEPS = [
  "Roteiro e narração em português",
  "Busca de mídia e legendas sincronizadas",
  "Montagem do primeiro MP4",
] as const;

const MANUAL_EDITS = ["Estilo das legendas", "Trilha sonora"] as const;

export function OperationalProof() {
  return (
    <section
      id="prova-operacional"
      role="region"
      aria-label="Prova operacional ClipIA"
      className="relative border-y border-white/8 bg-panel/35 py-14 sm:py-18"
    >
      <Container>
        <div className="grid items-center gap-10 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16">
          <Reveal>
            <div>
              <span className="inline-flex items-center gap-2 rounded-full border border-mint/25 bg-mint/8 px-3 py-1.5 font-mono text-[10px] uppercase tracking-[0.16em] text-mint">
                <Icon name="check" className="h-3.5 w-3.5" />
                Execução real medida em 14/07/2026
              </span>
              <h2 className="font-display mt-4 text-3xl font-extrabold leading-tight text-cloud sm:text-4xl">
                Do tema ao MP4, com o que foi automático e o que foi editado.
              </h2>
              <p className="mt-4 max-w-2xl text-base leading-relaxed text-mist">
                Tema original: <strong className="text-cloud">3 fatos surpreendentes sobre o cérebro</strong>. Template: <strong className="text-cloud">Narração + Stock</strong>, voz padrão.
              </p>

              <div className="mt-7 grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-azure/20 bg-azure/8 p-4">
                  <div className="font-mono text-[10px] uppercase tracking-wider text-azure">Geração automática</div>
                  <div className="font-display mt-1 text-2xl font-bold text-cloud">1 min 25 s</div>
                  <ul className="mt-3 space-y-2">
                    {AUTOMATED_STEPS.map((step) => (
                      <li key={step} className="flex items-start gap-2 text-xs leading-relaxed text-mist">
                        <Icon name="check" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-azure" />
                        {step}
                      </li>
                    ))}
                  </ul>
                </div>

                <div className="rounded-2xl border border-coral/20 bg-coral/8 p-4">
                  <div className="font-mono text-[10px] uppercase tracking-wider text-coral">2 ajustes manuais</div>
                  <div className="font-display mt-1 text-2xl font-bold text-cloud">6 min 48 s</div>
                  <p className="mt-1 text-[11px] text-mist-2">Tempo do export final após os ajustes</p>
                  <ul className="mt-3 space-y-2">
                    {MANUAL_EDITS.map((edit) => (
                      <li key={edit} className="flex items-start gap-2 text-xs leading-relaxed text-mist">
                        <Icon name="sparkles" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-coral" />
                        {edit}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <p className="mt-4 text-xs leading-relaxed text-mist-2">
                Medição de um único job no ambiente local. Fila, hardware, duração e provedores podem alterar os tempos; eles não são promessa de prazo.
              </p>
            </div>
          </Reveal>

          <Reveal delay={120} className="w-full">
            <div className="mx-auto max-w-[300px] overflow-hidden rounded-[2rem] border border-white/12 bg-ink shadow-[0_24px_80px_-32px_rgba(34,211,238,0.45)]">
              <video
                src="/showcase/prova-operacional-cerebro.mp4"
                poster="/showcase/posters/prova-operacional-cerebro.jpg"
                controls
                playsInline
                preload="metadata"
                className="aspect-[9/16] w-full bg-black object-cover"
                aria-label="MP4 final da prova operacional sobre o cérebro"
              />
            </div>
            <p className="mt-3 text-center font-mono text-[10px] text-mist-2">MP4 final · 26,9 s · 1080 × 1920</p>
          </Reveal>
        </div>
      </Container>
    </section>
  );
}
