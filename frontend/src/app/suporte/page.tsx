import type { Metadata } from 'next'

import { SUPPORT_EMAIL, SUPPORT_MAILTO, SUPPORT_WHATSAPP_URL } from '@/lib/support'

export const metadata: Metadata = {
  title: 'Suporte — ClipIA',
  description: 'Central de ajuda do ClipIA: perguntas frequentes e canais de contato (e-mail e WhatsApp).',
}

const FAQS = [
  {
    q: 'Como funciona a geração de vídeo?',
    a: 'Você informa um tema (ou escolhe um dos assuntos em alta), e o ClipIA gera roteiro, narração em português, legendas sincronizadas e mídia de fundo automaticamente. Em poucos minutos o vídeo aparece no seu dashboard, pronto para baixar ou ajustar no editor.',
  },
  {
    q: 'Como funcionam os créditos?',
    a: 'Cada geração consome créditos conforme o template e a voz escolhida (narração padrão custa 1 crédito; vozes premium e templates com imagem/vídeo de IA custam mais — o custo aparece antes de gerar). Créditos comprados não expiram.',
  },
  {
    q: 'Quais formas de pagamento vocês aceitam?',
    a: 'Pix e cartão de crédito, processados pelo Mercado Pago e pela Stripe. O ClipIA não armazena os dados do seu cartão. Os créditos caem na conta automaticamente em até ~30 segundos após a confirmação do pagamento.',
  },
  {
    q: 'O vídeo falhou ou não ficou bom. E agora?',
    a: 'Se a geração falhar por erro da plataforma, o crédito consumido é devolvido automaticamente. Se o vídeo ficou aquém do esperado, use o editor para ajustar cenas, voz e legendas — e conte pra gente pelo botão de feedback: cada relato melhora o produto.',
  },
  {
    q: 'Posso pedir reembolso de uma compra?',
    a: 'Estornos e chargebacks feitos junto ao provedor de pagamento revertem automaticamente os créditos daquela compra. Créditos já gastos em vídeos gerados e entregues não geram reembolso (bens digitais consumidos). Para casos excepcionais, fale com o suporte.',
  },
  {
    q: 'Como edito um vídeo depois de gerado?',
    a: 'No dashboard, clique em "Editar" no card do vídeo. O editor permite trocar mídia das cenas, regenerar a narração, ajustar legendas e elementos, com preview em tempo real. Ao exportar, o vídeo final é renderizado com fidelidade total ao preview.',
  },
]

export default function SuportePage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-16">
      <p className="text-xs uppercase tracking-[0.22em]" style={{ color: 'var(--accent-primary, #ff5638)' }}>
        Suporte
      </p>
      <h1 className="mt-2 text-3xl font-bold" style={{ color: 'var(--text-primary)' }}>
        Como podemos ajudar?
      </h1>
      <p className="mt-3 text-sm leading-6" style={{ color: 'var(--text-secondary)' }}>
        Estamos em beta e respondemos rápido. Confira as perguntas frequentes ou fale direto com a gente.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <a
          href={SUPPORT_MAILTO}
          className="rounded-2xl border p-5 transition hover:bg-white/5"
          style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}
        >
          <p className="text-2xl">✉️</p>
          <p className="mt-2 font-semibold" style={{ color: 'var(--text-primary)' }}>E-mail</p>
          <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>{SUPPORT_EMAIL}</p>
          <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>Resposta em até 1 dia útil</p>
        </a>
        <a
          href={SUPPORT_WHATSAPP_URL}
          target="_blank"
          rel="noreferrer"
          className="rounded-2xl border p-5 transition hover:bg-white/5"
          style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}
        >
          <p className="text-2xl">💬</p>
          <p className="mt-2 font-semibold" style={{ color: 'var(--text-primary)' }}>WhatsApp</p>
          <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)' }}>Fale com a gente no zap</p>
          <p className="mt-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>Horário comercial (BRT)</p>
        </a>
      </div>

      <h2 className="mt-12 text-xl font-semibold" style={{ color: 'var(--text-primary)' }}>
        Perguntas frequentes
      </h2>
      <div className="mt-4 space-y-3">
        {FAQS.map((item) => (
          <details
            key={item.q}
            className="group rounded-2xl border p-5"
            style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-surface)' }}
          >
            <summary
              className="cursor-pointer list-none text-sm font-semibold marker:hidden"
              style={{ color: 'var(--text-primary)' }}
            >
              {item.q}
            </summary>
            <p className="mt-3 text-sm leading-6" style={{ color: 'var(--text-secondary)' }}>
              {item.a}
            </p>
          </details>
        ))}
      </div>

      <p className="mt-10 text-sm" style={{ color: 'var(--text-secondary)' }}>
        Não achou o que precisava? Escreva para{' '}
        <a href={SUPPORT_MAILTO} className="underline" style={{ color: 'var(--accent-primary, #ff5638)' }}>
          {SUPPORT_EMAIL}
        </a>{' '}
        — toda mensagem é lida.
      </p>
    </div>
  )
}
