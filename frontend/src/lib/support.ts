// Canais de suporte do beta. O recebimento do e-mail exige Cloudflare Email Routing
// (Resend é send-only); o backend usa o mesmo endereço como Reply-To do welcome email
// (SUPPORT_EMAIL em app/config.py — manter os dois em sincronia).
export const SUPPORT_EMAIL = 'suporte@clipia.com.br'

// Só dígitos, formato wa.me (DDI+DDD+número).
export const SUPPORT_WHATSAPP_DIGITS = '5545998296112'

export const SUPPORT_WHATSAPP_URL = `https://wa.me/${SUPPORT_WHATSAPP_DIGITS}?text=${encodeURIComponent(
  'Olá! Preciso de ajuda com o ClipIA.',
)}`

export const SUPPORT_MAILTO = `mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent('Suporte ClipIA')}`
