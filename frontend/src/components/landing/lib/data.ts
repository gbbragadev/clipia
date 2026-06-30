// Single source of truth for page content. Only real product facts are included.

export const SITE = {
  name: "ClipIA",
  url: "https://www.clipia.com.br",
  signup: "/auth/register",
  login: "/auth/login",
  tagline: "Do tema ao vídeo vertical com IA",
};

export const NAV_LINKS = [
  { label: "Como funciona", href: "#como-funciona" },
  { label: "Demo", href: "#demo" },
  { label: "Exemplos", href: "#exemplos" },
  { label: "Diferenciais", href: "#diferenciais" },
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
  { icon: "gift", text: "2 vídeos grátis ao confirmar o e-mail" },
  { icon: "card", text: "Sem cartão de crédito" },
  { icon: "mic", text: "Narração pt-BR com vozes naturais" },
] as const;

export interface ValueProp {
  accent: Accent;
  icon: string;
  title: string;
  text: string;
}

export const VALUE_PROPS: ValueProp[] = [
  {
    accent: "coral",
    icon: "sparkles",
    title: "Do tema ao roteiro",
    text: "Você descreve o assunto e a IA estrutura o gancho, as cenas e a narração em português — sem começar do zero.",
  },
  {
    accent: "mint",
    icon: "caption",
    title: "Legendas que se movem",
    text: "Legendas sincronizadas palavra por palavra, em vários estilos animados, prontas para prender a atenção.",
  },
  {
    accent: "azure",
    icon: "layers",
    title: "Mídia de stock + IA",
    text: "Vídeos e imagens com licença livre (Pexels) e geração de imagem por IA. Uso comercial liberado.",
  },
  {
    accent: "coral",
    icon: "film",
    title: "Editar e publicar",
    text: "Refine no editor e exporte em MP4 vertical 9:16, pronto para Reels, TikTok e YouTube Shorts.",
  },
];

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

export interface Niche {
  id: string;
  label: string;
  emoji: string;
  desc: string;
  accent: Accent;
}

export const NICHES: Niche[] = [
  { id: "curiosidades", label: "Curiosidades", emoji: "🪐", desc: "Fatos e “você sabia?”", accent: "azure" },
  { id: "religioso", label: "Conteúdo Religioso", emoji: "🕊️", desc: "Mensagens e versículos", accent: "mint" },
  { id: "motivacional", label: "Motivacional", emoji: "🚀", desc: "Inspirar e incentivar", accent: "coral" },
  { id: "financas", label: "Finanças", emoji: "💸", desc: "Dinheiro e hábitos", accent: "mint" },
  { id: "misterio", label: "Histórias & Mistério", emoji: "🔮", desc: "Casos e enigmas", accent: "azure" },
  { id: "humor", label: "Humor", emoji: "😂", desc: "Riso e situações", accent: "coral" },
  { id: "drama", label: "Drama Histórico", emoji: "🏛️", desc: "Histórias do passado", accent: "azure" },
];

export const DURATIONS = [
  { s: 15, label: "15s" },
  { s: 30, label: "30s" },
  { s: 60, label: "60s" },
] as const;

export interface Voice {
  id: string;
  label: string;
  short: string;
  tier: "standard" | "premium";
  gender: "f" | "m";
  credits: number;
}

export const VOICES: Voice[] = [
  { id: "f-padrao", label: "Feminina · padrão", short: "Voz feminina", tier: "standard", gender: "f", credits: 1 },
  { id: "m-padrao", label: "Masculina · padrão", short: "Voz masculina", tier: "standard", gender: "m", credits: 1 },
  { id: "f-premium", label: "Feminina · premium", short: "Voz feminina premium", tier: "premium", gender: "f", credits: 2 },
  { id: "m-premium", label: "Masculina · premium", short: "Voz masculina premium", tier: "premium", gender: "m", credits: 2 },
];

export const CAPTION_STYLES = [
  { id: "pop", label: "Pop" },
  { id: "box", label: "Caixa" },
  { id: "underline", label: "Traço" },
] as const;

export const DIFFERENTIALS = [
  { icon: "globe", title: "100% no navegador", text: "Criação completa no desktop e no celular. Nada para instalar." },
  { icon: "film", title: "Editor integrado", text: "Ajuste cenas, mídia e legendas antes de baixar o arquivo final." },
  { icon: "mic", title: "Vozes em pt-BR", text: "Narração natural, com opções masculinas e femininas." },
  { icon: "caption", title: "Legendas palavra por palavra", text: "Sincronização precisa em vários estilos animados." },
  { icon: "layers", title: "Mídia com licença livre", text: "Stock (Pexels) e imagem por IA, com uso comercial liberado." },
  { icon: "bolt", title: "Créditos justos", text: "Você paga pela voz (padrão = 1, premium = 2), não pela duração." },
];

export const ANATOMY = [
  { icon: "layers", label: "Mídia", desc: "Stock com licença livre e imagem por IA" },
  { icon: "mic", label: "Narração pt-BR", desc: "Vozes naturais, masculina e feminina" },
  { icon: "caption", label: "Legendas", desc: "Sincronizadas palavra por palavra" },
  { icon: "film", label: "Edição", desc: "Cortes, ritmo e montagem no editor" },
  { icon: "download", label: "Exportação", desc: "MP4 vertical 9:16" },
];

export const SPECS = [
  { k: "Formato", v: "MP4 vertical 9:16 · Reels, TikTok, Shorts" },
  { k: "Narração", v: "pt-BR, vozes masculina e feminina" },
  { k: "Legendas", v: "Palavra por palavra, estilos animados" },
  { k: "Mídia", v: "Stock (Pexels) + imagem por IA · uso comercial" },
  { k: "Plataforma", v: "Navegador, desktop e celular" },
  { k: "Créditos", v: "Por voz, não por duração" },
];

export const FAQ_ITEMS = [
  {
    q: "Preciso de cartão de crédito para testar?",
    a: "Não. Você recebe 2 vídeos grátis ao confirmar o e-mail do cadastro. Sem cartão e sem compromisso.",
  },
  {
    q: "Como funcionam os créditos?",
    a: "Você começa com 2 créditos grátis no cadastro. Pacotes adicionais partem de R$19,90. Cada vídeo consome créditos pelo tipo de voz: voz padrão custa 1 crédito e voz premium custa 2. A duração do vídeo não altera o custo.",
  },
  {
    q: "Posso criar pelo celular?",
    a: "Sim. A criação é 100% pelo navegador, tanto no desktop quanto no celular. Você também usa o editor para refinar antes de baixar.",
  },
  {
    q: "Em que formato o vídeo é entregue?",
    a: "MP4 vertical 9:16, pronto para publicar em Reels, TikTok e YouTube Shorts.",
  },
  {
    q: "Que tipo de mídia é usado nos vídeos?",
    a: "Mídia de stock com licença livre (Pexels) e geração de imagem por IA. O uso comercial é liberado.",
  },
  {
    q: "As vozes são em português?",
    a: "Sim. A narração é em pt-BR, com vozes naturais masculinas e femininas.",
  },
  {
    q: "A IA garante que meu vídeo vai viralizar?",
    a: "Não. Não garantimos viralizar, alcance ou engajamento. A ClipIA acelera a criação do vídeo; o resultado depende do tema, do nicho e dos ajustes que você faz no editor.",
  },
  {
    q: "Quais nichos estão prontos?",
    a: "Curiosidades, Conteúdo Religioso, Motivacional, Finanças, Histórias & Mistério, Humor e Drama Histórico.",
  },
];

export const GALLERY = [
  { niche: "Curiosidades", title: "O espaço tem um cheiro?", duration: "30s", voice: "Feminina · padrão", img: "https://images.pexels.com/photos/25752810/pexels-photo-25752810.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1200&w=800", alt: "Nebulosa colorida com poeira cósmica no espaço profundo", accent: "azure" as Accent },
  { niche: "Motivacional", title: "Comece antes de se sentir pronto", duration: "30s", voice: "Masculina · padrão", img: "https://images.pexels.com/photos/33525484/pexels-photo-33525484.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1200&w=800", alt: "Silhueta de caminhante ao nascer do sol em paisagem ampla", accent: "coral" as Accent },
  { niche: "Finanças", title: "3 hábitos de quem sai das dívidas", duration: "15s", voice: "Feminina · premium", img: "https://images.pexels.com/photos/6764225/pexels-photo-6764225.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1200&w=800", alt: "Moedas douradas em close sobre superfície dourada", accent: "mint" as Accent },
  { niche: "Histórias & Mistério", title: "O caso que ninguém explica", duration: "60s", voice: "Masculina · premium", img: "https://images.pexels.com/photos/17331666/pexels-photo-17331666.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1200&w=800", alt: "Caminho de floresta envolto em névoa ao amanhecer", accent: "azure" as Accent },
  { niche: "Conteúdo Religioso", title: "Versículo do dia: fé que move", duration: "30s", voice: "Feminina · padrão", img: "https://images.pexels.com/photos/35711666/pexels-photo-35711666.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1200&w=800", alt: "Raios de sol atravessando nuvens dramáticas", accent: "mint" as Accent },
  { niche: "Drama Histórico", title: "O império que desmoronou", duration: "60s", voice: "Masculina · padrão", img: "https://images.pexels.com/photos/38146058/pexels-photo-38146058.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1200&w=800", alt: "Colunas antigas romanas contra o céu azul", accent: "azure" as Accent },
  { niche: "Humor", title: "Quando a segunda-feira chega", duration: "15s", voice: "Masculina · padrão", img: "https://images.pexels.com/photos/5349022/pexels-photo-5349022.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1200&w=800", alt: "Arte abstrata com respingos de cores vibrantes", accent: "coral" as Accent },
  { niche: "Curiosidades", title: "O que existe no fundo do mar", duration: "30s", voice: "Feminina · premium", img: "https://images.pexels.com/photos/35175954/pexels-photo-35175954.jpeg?auto=compress&cs=tinysrgb&fit=crop&h=1200&w=800", alt: "Bolhas subindo em água azul profunda", accent: "azure" as Accent },
];

export const FOOTER_COLS = [
  {
    title: "Produto",
    links: [
      { label: "Como funciona", href: "#como-funciona" },
      { label: "Demo", href: "#demo" },
      { label: "Exemplos", href: "#exemplos" },
      { label: "Diferenciais", href: "#diferenciais" },
      { label: "FAQ", href: "#faq" },
    ],
  },
  {
    title: "Nichos",
    links: NICHES.slice(0, 6).map((n) => ({ label: n.label, href: "#demo" })),
  },
];
