"use client";
import { Container } from "@/components/landing/ui/Container";
import { SectionHeading } from "@/components/landing/ui/SectionHeading";
import { Highlight } from "@/components/landing/ui/Highlight";
import { Button } from "@/components/landing/ui/Button";
import { Reveal } from "@/components/landing/Reveal";
import { Icon, type IconName } from "@/components/landing/icons";
import { useAb } from "@/components/landing/lib/ab";
import {
  BONUS_PERCENT,
  CREDIT_COSTS,
  CTA_LABEL,
  PACKAGES,
  formatBrl,
} from "@/components/landing/lib/data";
import { cn } from "@/components/landing/utils/cn";

export function Pricing() {
  const ab = useAb();

  return (
    <section id="preco" className="relative overflow-clip scroll-mt-20 py-20 sm:py-24">
      {/* fundo */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <div
          className="absolute left-1/2 top-1/3 h-[28rem] w-[28rem] -translate-x-1/2 opacity-50 blur-[130px]"
          style={{ background: "radial-gradient(circle, rgba(255,86,56,0.13), transparent 65%)" }}
        />
      </div>

      <Container>
        <SectionHeading
          eyebrow="Preço transparente"
          eyebrowIcon="card"
          accent="mint"
          align="center"
          title={<Highlight text="Sem mensalidade. *Você paga pelo vídeo.*" />}
          description="Créditos pré-pagos, compra única, e eles não expiram. O preço abaixo é o mesmo do checkout — sem surpresa."
        />

        {/* o que 1 crédito compra */}
        <Reveal delay={100}>
          <div className="mx-auto mt-10 flex max-w-3xl flex-wrap items-center justify-center gap-2.5">
            {CREDIT_COSTS.map((c) => (
              <span
                key={c.label}
                className="flex items-center gap-2 rounded-full border border-white/8 bg-panel/60 px-3.5 py-1.5 text-[13px] text-mist"
              >
                <Icon name={c.icon as IconName} className="h-4 w-4 text-azure" />
                {c.label}
                <span className="font-mono text-[11px] text-cloud">
                  {c.credits} {c.credits === 1 ? "crédito" : "créditos"}
                </span>
              </span>
            ))}
          </div>
        </Reveal>

        {/* promo real (desligável em runtime via public/ab/headlines.json) */}
        {ab.showBonusBadge && (
          <Reveal delay={140}>
            <p className="mt-6 text-center">
              <span className="inline-flex items-center gap-2 rounded-full border border-mint/30 bg-mint/10 px-4 py-2 text-sm text-mint">
                <Icon name="gift" className="h-4 w-4" />
                +{BONUS_PERCENT}% de créditos bônus em toda compra — promoção de lançamento
              </span>
            </p>
          </Reveal>
        )}

        {/* pacotes (espelho de app/payments/schemas.py) */}
        <div className="mt-12 grid items-stretch gap-5 md:grid-cols-3 lg:gap-6">
          {PACKAGES.map((pkg, i) => {
            const perVideo = pkg.priceBrl / pkg.credits;
            const bonus = Math.floor((pkg.credits * BONUS_PERCENT) / 100);
            return (
              <Reveal key={pkg.id} delay={i * 110} className="h-full">
                <div
                  className={cn(
                    "relative flex h-full flex-col rounded-3xl border p-6 sm:p-8",
                    pkg.featured
                      ? "border-coral/45 bg-panel shadow-[0_0_60px_-18px_rgba(255,86,56,0.45)] lg:-translate-y-2"
                      : "border-white/8 bg-panel/70"
                  )}
                >
                  {pkg.featured && (
                    <span className="absolute -top-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-coral px-3 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-ink">
                      Mais escolhido
                    </span>
                  )}

                  <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-mist-2">
                    {pkg.name}
                  </div>

                  <div className="font-display mt-3 text-4xl font-extrabold tracking-tight text-cloud">
                    {formatBrl(pkg.priceBrl)}
                  </div>
                  <div className="mt-1 text-[13px] text-mist-2">pagamento único · Pix ou cartão</div>

                  <div className="mt-5 flex items-center gap-2">
                    <span className="text-lg font-semibold text-cloud">{pkg.credits} créditos</span>
                    {ab.showBonusBadge && bonus > 0 && (
                      <span className="rounded-full bg-mint/12 px-2 py-0.5 font-mono text-[11px] text-mint">
                        +{bonus} de bônus
                      </span>
                    )}
                  </div>

                  <div className="mt-1.5 text-sm text-mist">
                    ≈ <span className="font-semibold text-cloud">{formatBrl(perVideo)}</span> por
                    vídeo com voz padrão
                  </div>

                  <p className="mt-4 flex-1 text-sm leading-relaxed text-mist">{pkg.blurb}</p>

                  <div className="mt-6">
                    <Button
                      href={ab.signup(`preco-${pkg.id}`)}
                      variant={pkg.featured ? "primary" : "secondary"}
                      fullWidth
                      iconRight="arrowRight"
                    >
                      {CTA_LABEL}
                    </Button>
                  </div>
                </div>
              </Reveal>
            );
          })}
        </div>

        {/* letras nada miúdas */}
        <Reveal delay={160}>
          <div className="mx-auto mt-10 flex max-w-3xl flex-wrap items-center justify-center gap-x-6 gap-y-2 text-[13px] text-mist">
            {[
              "Compra única — sem assinatura",
              "Créditos não expiram",
              "Mercado Pago (Pix e cartão) ou Stripe (cartão)",
            ].map((t) => (
              <span key={t} className="flex items-center gap-1.5">
                <Icon name="check" className="h-4 w-4 text-mint" />
                {t}
              </span>
            ))}
            <a href="/termos" className="text-mist underline decoration-white/20 underline-offset-4 transition-colors hover:text-cloud">
              Termos e política de reembolso →
            </a>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
