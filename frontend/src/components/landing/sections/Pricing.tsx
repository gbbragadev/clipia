"use client";

import { useEffect, useMemo, useState } from "react";
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
  PACKAGES,
  formatBrl,
} from "@/components/landing/lib/data";
import { cn } from "@/components/landing/utils/cn";
import { fetchPackages, type CreditPackage } from "@/lib/payments";

type VoiceChoice = "standard_voice" | "premium_voice";
type MediaChoice = "stock" | "ai_image" | "ai_video";

const PACKAGE_BLURBS = Object.fromEntries(PACKAGES.map((pkg) => [pkg.id, pkg.blurb]));

function videosCovered(pkg: CreditPackage, voice: VoiceChoice, media: MediaChoice): number {
  const voiceLimit = pkg.equivalences[voice];
  if (media === "stock") return voiceLimit;
  return Math.min(voiceLimit, pkg.equivalences[media]);
}

function videoCountLabel(count: number): string {
  if (count === 0) return "0 vídeos completos";
  if (count === 1) return "Até 1 vídeo";
  return `Até ${count} vídeos`;
}

export function Pricing() {
  const ab = useAb();
  const [packages, setPackages] = useState<CreditPackage[] | null>(null);
  const [packagesFailed, setPackagesFailed] = useState(false);
  const [voice, setVoice] = useState<VoiceChoice>("standard_voice");
  const [media, setMedia] = useState<MediaChoice>("stock");

  useEffect(() => {
    let active = true;
    fetchPackages()
      .then((data) => {
        if (data.length === 0 || data.some((pkg) => !pkg.equivalences)) {
          throw new Error("Pacotes públicos incompletos");
        }
        if (active) setPackages(data);
      })
      .catch(() => {
        if (active) setPackagesFailed(true);
      });
    return () => {
      active = false;
    };
  }, []);

  const cards = useMemo(() => {
    if (packages) {
      return packages.map((pkg) => ({
        id: pkg.selected_package,
        name: pkg.name,
        priceBrl: pkg.price_brl / 100,
        credits: pkg.base_credits,
        totalCredits: pkg.total_credits,
        bonus: pkg.bonus_credits,
        featured: pkg.selected_package === "popular",
        blurb: PACKAGE_BLURBS[pkg.selected_package] ?? "Créditos pré-pagos que não expiram.",
      }));
    }
    return PACKAGES.map((pkg) => {
      const bonus = Math.floor((pkg.credits * BONUS_PERCENT) / 100);
      return { ...pkg, totalCredits: pkg.credits + bonus, bonus };
    });
  }, [packages]);

  const activeBonusPercent = packages?.[0]?.bonus_percent ?? BONUS_PERCENT;

  return (
    <section id="preco" className="relative overflow-clip scroll-mt-20 py-20 sm:py-24">
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

        <Reveal delay={100}>
          <div className="mx-auto mt-10 flex max-w-3xl flex-wrap items-center justify-center gap-2.5">
            {CREDIT_COSTS.map((cost) => (
              <span
                key={cost.label}
                className="flex items-center gap-2 rounded-full border border-white/8 bg-panel/60 px-3.5 py-1.5 text-[13px] text-mist"
              >
                <Icon name={cost.icon as IconName} className="h-4 w-4 text-azure" />
                {cost.label}
                <span className="font-mono text-[11px] text-cloud">
                  {cost.credits} {cost.credits === 1 ? "crédito" : "créditos"}
                </span>
              </span>
            ))}
          </div>
        </Reveal>

        <Reveal delay={120}>
          <div
            role="region"
            aria-label="Calculadora de créditos"
            className="mx-auto mt-8 max-w-4xl rounded-3xl border border-white/10 bg-panel/70 p-5 sm:p-7"
          >
            <div className="text-center">
              <h3 className="font-display text-xl font-bold text-cloud">Quantos vídeos cada pacote rende?</h3>
              <p className="mt-1 text-sm text-mist">Escolha a voz e a mídia. O cálculo usa créditos totais e mostra vídeos completos.</p>
            </div>

            <div className="mt-6 grid gap-5 md:grid-cols-2">
              <fieldset>
                <legend className="mb-2 text-sm font-semibold text-cloud">Narração</legend>
                <div className="grid grid-cols-2 gap-2">
                  {([
                    ["standard_voice", "Voz padrão"],
                    ["premium_voice", "Voz premium"],
                  ] as const).map(([value, label]) => (
                    <label key={value} className={cn(
                      "relative cursor-pointer overflow-hidden rounded-xl border px-3 py-3 text-center text-sm transition-colors",
                      voice === value ? "border-azure/60 bg-azure/12 text-cloud" : "border-white/8 bg-ink/30 text-mist",
                    )}>
                      <input
                        type="radio"
                        name="calculator-voice"
                        value={value}
                        checked={voice === value}
                        onChange={() => setVoice(value)}
                        className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                      />
                      {label}
                    </label>
                  ))}
                </div>
              </fieldset>

              <fieldset>
                <legend className="mb-2 text-sm font-semibold text-cloud">Mídia</legend>
                <div className="grid grid-cols-3 gap-2">
                  {([
                    ["stock", "Banco de vídeos"],
                    ["ai_image", "Imagens por IA"],
                    ["ai_video", "Vídeo por IA"],
                  ] as const).map(([value, label]) => (
                    <label key={value} className={cn(
                      "relative cursor-pointer overflow-hidden rounded-xl border px-2 py-3 text-center text-xs transition-colors sm:text-sm",
                      media === value ? "border-mint/60 bg-mint/10 text-cloud" : "border-white/8 bg-ink/30 text-mist",
                    )}>
                      <input
                        type="radio"
                        name="calculator-media"
                        value={value}
                        checked={media === value}
                        onChange={() => setMedia(value)}
                        className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                      />
                      {label}
                    </label>
                  ))}
                </div>
              </fieldset>
            </div>

            {packages ? (
              <div className="mt-6 grid gap-3 sm:grid-cols-3" aria-live="polite">
                {packages.map((pkg) => {
                  const count = videosCovered(pkg, voice, media);
                  return (
                    <div
                      key={pkg.id}
                      data-testid={`calculator-${pkg.selected_package}`}
                      className="rounded-2xl border border-white/8 bg-ink/35 p-4 text-center"
                    >
                      <div className="text-sm text-mist">{pkg.name}</div>
                      <div className={cn("mt-1 font-display text-xl font-bold", count === 0 ? "text-coral" : "text-mint")}>{videoCountLabel(count)}</div>
                      <div className="mt-1 font-mono text-[10px] text-mist-2">{pkg.total_credits} créditos disponíveis</div>
                    </div>
                  );
                })}
              </div>
            ) : packagesFailed ? (
              <p className="mt-6 text-center text-sm text-coral" role="status">Calculadora temporariamente indisponível.</p>
            ) : (
              <p className="mt-6 text-center text-sm text-mist" role="status">Atualizando pacotes…</p>
            )}
          </div>
        </Reveal>

        {ab.showBonusBadge && (
          <Reveal delay={140}>
            <p className="mt-6 text-center">
              <span className="inline-flex items-center gap-2 rounded-full border border-mint/30 bg-mint/10 px-4 py-2 text-sm text-mint">
                <Icon name="gift" className="h-4 w-4" />
                +{activeBonusPercent}% de créditos bônus em toda compra — promoção de lançamento
              </span>
            </p>
          </Reveal>
        )}

        <div className="mt-12 grid items-stretch gap-5 md:grid-cols-3 lg:gap-6">
          {cards.map((pkg, index) => {
            const perVideo = pkg.priceBrl / pkg.totalCredits;
            return (
              <Reveal key={pkg.id} delay={index * 110} className="h-full">
                <div className={cn(
                  "relative flex h-full flex-col rounded-3xl border p-6 sm:p-8",
                  pkg.featured
                    ? "border-coral/45 bg-panel shadow-[0_0_60px_-18px_rgba(255,86,56,0.45)] lg:-translate-y-2"
                    : "border-white/8 bg-panel/70",
                )}>
                  {pkg.featured && (
                    <span className="absolute -top-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-coral px-3 py-1 font-mono text-[10px] font-semibold uppercase tracking-wider text-ink">Mais escolhido</span>
                  )}
                  <div className="font-mono text-[11px] uppercase tracking-[0.18em] text-mist-2">{pkg.name}</div>
                  <div className="font-display mt-3 text-4xl font-extrabold tracking-tight text-cloud">{formatBrl(pkg.priceBrl)}</div>
                  <div className="mt-1 text-[13px] text-mist-2">pagamento único · Pix e cartão</div>
                  <div className="mt-5 flex items-center gap-2">
                    <span className="text-lg font-semibold text-cloud">{pkg.credits} créditos</span>
                    {ab.showBonusBadge && pkg.bonus > 0 && (
                      <span className="rounded-full bg-mint/12 px-2 py-0.5 font-mono text-[11px] text-mint">+{pkg.bonus} de bônus</span>
                    )}
                  </div>
                  <div className="mt-1.5 text-sm text-mist">a partir de <span className="font-semibold text-cloud">{formatBrl(perVideo)}</span> por vídeo com voz padrão</div>
                  <p className="mt-4 flex-1 text-sm leading-relaxed text-mist">{pkg.blurb}</p>
                  <div className="mt-6">
                    <Button
                      href={ab.signup(`pricing-${pkg.id}`, pkg.id)}
                      variant={pkg.featured ? "primary" : "secondary"}
                      fullWidth
                      iconRight="arrowRight"
                    >
                      Escolher {pkg.name}
                    </Button>
                  </div>
                </div>
              </Reveal>
            );
          })}
        </div>

        <Reveal delay={160}>
          <div className="mx-auto mt-10 flex max-w-3xl flex-wrap items-center justify-center gap-x-6 gap-y-2 text-[13px] text-mist">
            {["Compra única — sem assinatura", "Créditos não expiram", "Mercado Pago (Pix e cartão) ou Stripe (cartão)"].map((text) => (
              <span key={text} className="flex items-center gap-1.5">
                <Icon name="check" className="h-4 w-4 text-mint" />
                {text}
              </span>
            ))}
            <a href="/termos#creditos-e-reembolsos" className="text-mist underline decoration-white/20 underline-offset-4 transition-colors hover:text-cloud">Termos e política de reembolso →</a>
          </div>
        </Reveal>
      </Container>
    </section>
  );
}
