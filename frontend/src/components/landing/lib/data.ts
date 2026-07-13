// Single source of truth for page content. Only real product facts are included.
// Preços/créditos espelham app/payments/schemas.py e app/config.py (fonte de verdade
// do backend) — se o backend mudar, atualizar aqui.

export const SITE = {
  name: "ClipIA",
  url: "https://www.clipia.com.br",
  signup: "/auth/register",
  login: "/auth/login",
  dashboard: "/dashboard",
  tagline: "Do tema ao vídeo vertical com IA",
};

/** Link SSR seguro; o AbProvider acrescenta atribuicao externa sem sobrescreve-la. */
export function signupUrl(content: string): string {
  return `${SITE.signup}?placement=${encodeURIComponent(content)}`;
}

export const CTA_LABEL = "Criar vídeo grátis";

/** Claim de gratuidade — sem número fixo até a decisão de WELCOME_CREDIT_BONUS.
 * Pode ser sobrescrito em produção via public/ab/headlines.json (knobs.freeClaim). */
export const FREE_CLAIM =
  "Comece com 2 créditos grátis — até 2 vídeos com voz padrão. Sem cartão.";

export const NAV_LINKS = [
  { label: "Antes e depois", href: "#prova" },
  { label: "Para quem", href: "#para-quem" },
  { label: "Como funciona", href: "#como-funciona" },
  { label: "Preço", href: "#preco" },
  { label: "Exemplos", href: "/exemplos" },
  { label: "FAQ", href: "#faq" },
] as const;

export type Accent = "coral" | "azure" | "mint";

export const accentMap: Record<
  Accent,
  { text: string; bg: string; soft: string; border: string; dot: string; glow: string }
> = {
  coral: {
    text: "text-coral",
    bg: "bg-coral",
    soft: "bg-coral/12",
    border: "border-coral/40",
    dot: "bg-coral",
    glow: "shadow-[0_0_30px_-8px_rgba(255,86,56,0.55)]",
  },
  azure: {
    text: "text-azure",
    bg: "bg-azure",
    soft: "bg-azure/12",
    border: "border-azure/40",
    dot: "bg-azure",
    glow: "shadow-[0_0_30px_-8px_rgba(62,155,255,0.5)]",
  },
  mint: {
    text: "text-mint",
    bg: "bg-mint",
    soft: "bg-mint/12",
    border: "border-mint/40",
    dot: "bg-mint",
    glow: "shadow-[0_0_30px_-8px_rgba(67,224,173,0.45)]",
  },
};

export const HERO_FACTS = [
  { icon: "gift", text: "Créditos de boas-vindas ao confirmar o e-mail" },
  { icon: "card", text: "Sem cartão para começar" },
  { icon: "mic", text: "Narração pt-BR com vozes naturais" },
] as const;

/* ── Vídeos reais do showcase (vivem em frontend/public/showcase/) ──
 * beforeScript = o tema/gancho cru que gerou o vídeo — é a prova antes→depois. */
export interface ShowcaseVideo {
  id: string;
  src: string;
  title: string;
  chip: string;
  emoji: string;
  beforeScript: string;
  accent: Accent;
  /** Frame real 540×960 (gerado dos MP4s): pintura imediata + zero download. */
  poster: string;
}

export const SHOWCASE_HERO: ShowcaseVideo[] = [
  {
    id: "cerebro",
    src: "/showcase/cerebro-fatos.mp4",
    poster: "/showcase/posters/cerebro.jpg",
    title: "Fatos surpreendentes sobre o cérebro",
    chip: "Cérebro",
    emoji: "🧠",
    beforeScript: "Seu cérebro mente para você o dia inteiro.",
    accent: "coral",
  },
  {
    id: "ocean",
    src: "/showcase/ocean-curiosidades.mp4",
    poster: "/showcase/posters/ocean.jpg",
    title: "5 curiosidades sobre o oceano profundo",
    chip: "Oceano",
    emoji: "🌊",
    beforeScript: "Você sabia que conhecemos menos de 5% dos oceanos?",
    accent: "azure",
  },
  {
    id: "ia",
    src: "/showcase/ia-revolucao.mp4",
    poster: "/showcase/posters/ia.jpg",
    title: "Como a IA está mudando o mundo",
    chip: "IA",
    emoji: "🤖",
    beforeScript: "A IA não vai te substituir. Mas quem usa IA, vai.",
    accent: "mint",
  },
];

/* ── Barra de fatos (só o objetivamente verificável no produto) ── */
export const FACTS = [
  { icon: "film", text: "MP4 vertical 9:16" },
  { icon: "mic", text: "Narração em português" },
  { icon: "caption", text: "Legendas palavra por palavra" },
  { icon: "edit", text: "Editor completo incluso" },
  { icon: "layers", text: "10 templates de vídeo" },
  { icon: "bolt", text: "Créditos não expiram" },
  { icon: "card", text: "Pix e cartão" },
  { icon: "globe", text: "100% no navegador" },
] as const;

/* ── Personas (seções de chamada por público) ── */
export interface Persona {
  id: "criador" | "agencia" | "local";
  index: string;
  label: string;
  accent: Accent;
  paragraphs: string[];
  bullets: string[];
  visual: "showcase" | "editor" | "prompt";
}

export const PERSONAS: Persona[] = [
  {
    id: "criador",
    index: "01",
    label: "Criador de conteúdo",
    accent: "coral",
    paragraphs: [
      "Editar um Short leva mais tempo que gravar dez. Canal sem frequência é canal parado — e cada vídeo que você não posta porque a edição comeu a noite é um vídeo que não existe.",
      "No ClipIA, o tema vira vídeo narrado e legendado. Você só ajusta o que quiser no editor — e volta a postar no ritmo que o seu canal pede.",
    ],
    bullets: [
      "Nichos prontos: curiosidades, histórias, motivacional, finanças e mais",
      "Narração em português — sem aparecer e sem gravar",
      "1 crédito por vídeo com voz padrão",
    ],
    visual: "showcase",
  },
  {
    id: "agencia",
    index: "02",
    label: "Social media & agências",
    accent: "azure",
    paragraphs: [
      "Três clientes de Reels não deviam significar um CapCut aberto até duas da manhã.",
      "A pauta do cliente entra no ClipIA e sai uma fila de vídeos com narração e legenda. Você revisa no editor — cenas, voz, legendas, elementos — e entrega. Produção vira revisão.",
    ],
    bullets: [
      "Editor completo para ajustar ao gosto de cada cliente",
      "Vozes diferentes por projeto (padrão e premium)",
      "Créditos avulsos — sem mensalidade por cliente",
    ],
    visual: "editor",
  },
  {
    id: "local",
    index: "03",
    label: "Negócios locais",
    accent: "mint",
    paragraphs: [
      "Você sabe que precisa postar. Só não sabe o quê — e não tem tempo de gravar.",
      "Digite o assunto da semana, como “5 erros ao reformar um banheiro”, e receba o vídeo com narração e legenda, pronto para o perfil do negócio.",
    ],
    bullets: [
      "Do assunto ao vídeo publicável em minutos",
      "Sem câmera, sem estúdio, sem contratar agência",
      "Comece grátis e pague só pelos vídeos que gerar",
    ],
    visual: "prompt",
  },
];

/* ── Preço (espelho de app/payments/schemas.py + app/pricing.py) ── */
export const BONUS_PERCENT = 20; // PURCHASE_BONUS_PERCENT ativo no backend (promo de lançamento)

export const CREDIT_COSTS = [
  { icon: "mic", label: "Voz padrão", credits: 1 },
  { icon: "sparkles", label: "Voz premium", credits: 2 },
  { icon: "wand", label: "Imagens por IA", credits: 5 },
  { icon: "film", label: "Vídeo por IA", credits: 30 },
] as const;

export interface CreditPackage {
  id: "starter" | "popular" | "professional";
  name: string;
  credits: number;
  priceBrl: number; // em reais
  blurb: string;
  featured?: boolean;
}

export const PACKAGES: CreditPackage[] = [
  { id: "starter", name: "Starter", credits: 10, priceBrl: 19.9, blurb: "Para testar de verdade" },
  {
    id: "popular",
    name: "Popular",
    credits: 30,
    priceBrl: 49.9,
    blurb: "30 vídeos com voz padrão — um por dia, o mês inteiro",
    featured: true,
  },
  { id: "professional", name: "Profissional", credits: 100, priceBrl: 129.9, blurb: "Volume de canal — o menor preço por vídeo" },
];

export function formatBrl(value: number): string {
  return `R$ ${value.toFixed(2).replace(".", ",")}`;
}

/* ── Passos (Como funciona) ── */
export interface Step {
  accent: Accent;
  n: string;
  title: string;
  text: string;
}

export const STEPS: Step[] = [
  {
    accent: "coral",
    n: "01",
    title: "Descreva o tema e o nicho",
    text: "Digite o assunto e escolha entre nichos prontos: Curiosidades, Motivacional, Finanças, Religioso e outros.",
  },
  {
    accent: "azure",
    n: "02",
    title: "A IA monta o vídeo",
    text: "Roteiro, cenas, narração em pt-BR, legendas animadas e mídia são gerados e sincronizados automaticamente.",
  },
  {
    accent: "mint",
    n: "03",
    title: "Refine e baixe",
    text: "Use o editor para ajustar e exporte o MP4 vertical 9:16 direto no navegador, no desktop ou no celular.",
  },
];

/* ── Nichos (slugs = páginas SEO reais em /criar/[nicho]) ── */
export interface Niche {
  id: string;
  label: string;
  emoji: string;
  desc: string;
  accent: Accent;
  href: string;
}

export const NICHES: Niche[] = [
  { id: "curiosidades", label: "Curiosidades", emoji: "🪐", desc: "Fatos e “você sabia?”", accent: "azure", href: "/criar/curiosidades" },
  { id: "religioso", label: "Conteúdo Religioso", emoji: "🕊️", desc: "Mensagens e versículos", accent: "mint", href: "/criar/religioso" },
  { id: "motivacional", label: "Motivacional", emoji: "🚀", desc: "Inspirar e incentivar", accent: "coral", href: "/criar/motivacional" },
  { id: "financas", label: "Finanças", emoji: "💸", desc: "Dinheiro e hábitos", accent: "mint", href: "/criar/financas" },
  { id: "historias", label: "Histórias & Mistério", emoji: "🔮", desc: "Casos e enigmas", accent: "azure", href: "/criar/historias" },
  { id: "humor", label: "Humor", emoji: "😂", desc: "Riso e situações", accent: "coral", href: "/criar/humor" },
  { id: "drama", label: "Drama Histórico", emoji: "🏛️", desc: "Histórias do passado", accent: "azure", href: "/criar/drama" },
];

/* ── FAQ (respostas honestas — políticas reais de /termos) ── */
export const FAQ_ITEMS = [
  {
    q: "O que eu ganho ao criar a conta?",
    a: FREE_CLAIM,
  },
  {
    q: "Como funcionam os créditos?",
    a: "Você compra um pacote uma única vez (a partir de R$ 19,90) e gasta créditos por vídeo: voz padrão custa 1 crédito, voz premium 2, template de imagens por IA 5 e o template de vídeo por IA 30. A duração do vídeo não altera o custo.",
  },
  {
    q: "Créditos expiram? Existe mensalidade?",
    a: "Não e não. Não existe assinatura: você compra créditos quando quiser e eles não expiram.",
  },
  {
    q: "Como eu pago? Tem Pix?",
    a: "Sim. O checkout aceita Pix e cartão via Mercado Pago, ou cartão via Stripe. Pagamento único, sem recorrência.",
  },
  {
    q: "E se eu pedir estorno?",
    a: "Estornos e chargebacks feitos junto ao provedor de pagamento revertem automaticamente os créditos daquela compra. Créditos já gastos em vídeos gerados e entregues não geram reembolso (bem digital consumido). Casos excepcionais: fale com o suporte.",
  },
  {
    q: "O vídeo é meu? Posso usar comercialmente?",
    a: "Sim. A mídia vem de banco com licença livre (Pexels) ou é gerada por IA, e o uso comercial é liberado.",
  },
  {
    q: "Os vídeos levam marca do ClipIA?",
    a: "Todo vídeo termina com uma vinheta discreta do ClipIA de cerca de 1,5 segundo. O conteúdo do seu vídeo não recebe marca d’água.",
  },
  {
    q: "Posso criar pelo celular?",
    a: "Sim. A criação é 100% pelo navegador, no desktop e no celular — incluindo o editor.",
  },
  {
    q: "A IA garante que meu vídeo vai viralizar?",
    a: "Não. Não garantimos viralizar, alcance ou engajamento. O ClipIA acelera a criação do vídeo; o resultado depende do tema, do nicho e dos ajustes que você faz no editor.",
  },
  {
    q: "Quais nichos estão prontos?",
    a: "Curiosidades, Conteúdo Religioso, Motivacional, Finanças, Histórias & Mistério, Humor e Drama Histórico — cada um com página de exemplos reais.",
  },
];

/* ── Variantes A/B (defaults embutidos; sobrescreva em public/ab/headlines.json).
 * Trecho entre *asteriscos* é destacado em coral pelo componente <Highlight>. ── */
export type AbVariant = "A" | "B" | "C";
export type AbSection = "hero" | "criador" | "agencia" | "local";

export const AB_DEFAULTS: Record<AbSection, Record<AbVariant, string>> = {
  hero: {
    A: "Digite o tema. *Baixe o vídeo pronto.*",
    B: "Sua ideia vira um *Reel narrado e legendado* em minutos.",
    C: "Este vídeo foi feito *inteiro por IA*. Crie o seu.",
  },
  criador: {
    A: "Você não precisa de editor. *Precisa de volume.*",
    B: "*Sua semana de vídeos* em uma tarde.",
    C: "Pare de perder a noite *editando um único Short*.",
  },
  agencia: {
    A: "Escale clientes, *não madrugadas*.",
    B: "A pauta do cliente entra. *A fila de Reels sai.*",
    C: "Mais clientes de vídeo, *sem contratar editor*.",
  },
  local: {
    A: "Seu negócio postando toda semana, *sem você aparecer*.",
    B: "Quem não posta, não é lembrado. *Poste sem aparecer.*",
    C: "Vídeo para o seu negócio: *sem câmera, sem editor*.",
  },
};

export const FOOTER_COLS = [
  {
    title: "Produto",
    links: [
      { label: "Antes e depois", href: "#prova" },
      { label: "Para quem", href: "#para-quem" },
      { label: "Como funciona", href: "#como-funciona" },
      { label: "Preço", href: "#preco" },
      { label: "Exemplos", href: "/exemplos" },
      { label: "Suporte", href: "/suporte" },
      { label: "Termos de uso", href: "/termos" },
      { label: "Privacidade", href: "/privacidade" },
    ],
  },
  {
    title: "Nichos",
    links: NICHES.map((n) => ({ label: n.label, href: n.href })),
  },
];
