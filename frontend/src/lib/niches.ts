// Manifesto de nichos — fonte da verdade do conteudo SEO das paginas /criar/[nicho].
// O vocabulario de `slug` aqui e o mesmo usado no campo `niche` do showcase.json.
// Conteudo deve ser UNICO por nicho (anti thin-content). Ver plano em
// ~/.claude/plans/vamos-planejar-temporal-naur.md.

export interface NicheFAQ {
  question: string
  answer: string
}

export interface NicheBenefit {
  title: string
  description: string
}

export interface NicheStep {
  step: number
  title: string
  description: string
}

export interface NicheContent {
  slug: string // "curiosidades" — = id do niche no showcase.json
  label: string
  emoji: string
  accent: string // hex p/ PretextHeading/badges
  gradient: string // classes tailwind do fundo do hero
  recommendedTemplate: string // id em app/templates.py
  generateStyle: 'educational' | 'storytelling' | 'news' | 'comedy'
  metaTitle: string // ~60 chars, com keyword
  metaDescription: string // ~155 chars
  h1: string
  heroSubtitle: string
  intro: string // 2-3 paragrafos (separados por \n\n)
  benefits: NicheBenefit[]
  howItWorks: NicheStep[]
  exampleTopics: string[]
  faqs: NicheFAQ[]
}

const baseHowItWorks = (themeExample: string): NicheStep[] => [
  { step: 1, title: 'Escreva o tema', description: `Digite o assunto do seu vídeo. Ex.: "${themeExample}".` },
  { step: 2, title: 'A IA escreve o roteiro', description: 'O roteiro sai com gancho nos 3 primeiros segundos e ritmo pensado para retenção.' },
  { step: 3, title: 'Narração, legendas e mídia', description: 'Narração em pt-BR, legendas sincronizadas palavra por palavra e mídia selecionada automaticamente.' },
  { step: 4, title: 'Ajuste no editor', description: 'Troque cenas, mude o estilo de legenda, regenere a voz e adicione elementos — o que você vê é o que exporta.' },
  { step: 5, title: 'Baixe e publique', description: 'Exporte em 9:16 e suba direto no YouTube Shorts, Reels e TikTok.' },
]

const sharedFaq = (): NicheFAQ[] => [
  {
    question: 'Preciso saber editar vídeo?',
    answer: 'Não. O ClipIA cria o vídeo completo a partir de um tema — roteiro, narração, legendas e mídia. O editor é opcional, para quando você quiser refinar algum detalhe.',
  },
  {
    question: 'A narração é em português do Brasil?',
    answer: 'Sim. São vozes pt-BR naturais (não robóticas), com opções masculinas e femininas. Você escolhe a voz antes de gerar e pode trocar no editor.',
  },
  {
    question: 'Quanto custa para começar?',
    answer: 'Você ganha créditos de boas-vindas ao criar a conta, sem cartão de crédito — cada crédito gera um vídeo completo. Depois, pacotes de créditos a partir de R$19,90, sem assinatura.',
  },
  {
    question: 'Posso usar os vídeos comercialmente?',
    answer: 'Sim. O vídeo gerado é seu. A mídia de stock vem do Pexels (licença livre) e a narração é gerada para o seu uso.',
  },
]

export const NICHES: NicheContent[] = [
  {
    slug: 'curiosidades',
    label: 'Curiosidades',
    emoji: '🧠',
    accent: '#22d3ee',
    gradient: 'from-blue-900/40 to-cyan-900/40',
    recommendedTemplate: 'stock_narration',
    generateStyle: 'educational',
    metaTitle: 'Como Criar Vídeos de Curiosidades com IA | ClipIA',
    metaDescription:
      'Crie vídeos de curiosidades para YouTube Shorts, Reels e TikTok em minutos. Roteiro, narração em português e legendas animadas automáticos. Comece grátis, sem cartão.',
    h1: 'Crie vídeos de curiosidades automaticamente',
    heroSubtitle: 'Do tema ao Short pronto em minutos — sem roteirista e sem editor de vídeo.',
    intro:
      'Curiosidades estão entre os formatos que mais viralizam em vídeo curto: prendem a atenção, geram comentários e fazem o espectador assistir até o fim para descobrir o desfecho. O problema é o trabalho por trás — pesquisar o fato, escrever um roteiro com gancho, gravar a narração e sincronizar tudo com a edição.\n\nO ClipIA resolve isso de ponta a ponta. Você escreve o tema (por exemplo, "5 curiosidades sobre o oceano profundo") e a IA monta o roteiro, gera a narração em português, cria as legendas palavra por palavra e seleciona a mídia de fundo. Em poucos minutos você tem um vídeo no formato 9:16, pronto para publicar.\n\nÉ o jeito mais rápido de manter um canal de curiosidades ativo com 1, 2 ou 3 vídeos por dia, mantendo qualidade e sem depender de um editor.',
    benefits: [
      { title: 'Gancho nos 3 primeiros segundos', description: 'O roteiro já nasce pensado para retenção: a primeira frase fisga e o ritmo segura até o final.' },
      { title: 'Sem pesquisa manual', description: 'A IA organiza os fatos em frases curtas e impactantes — você só escolhe o tema.' },
      { title: 'Legendas que aumentam retenção', description: 'Legendas animadas, sincronizadas por palavra, no estilo que mais funciona em Shorts e Reels.' },
      { title: 'Pronto para todas as plataformas', description: 'Formato vertical 9:16 ideal para YouTube Shorts, Instagram Reels, TikTok e Kwai.' },
    ],
    howItWorks: baseHowItWorks('5 curiosidades sobre o oceano profundo'),
    exampleTopics: [
      '5 curiosidades sobre o oceano profundo',
      'Fatos sobre o cérebro humano que parecem mentira',
      'Curiosidades do espaço que ninguém te contou',
      'Animais com habilidades que parecem superpoderes',
      'Coisas do corpo humano que você não sabia',
      'Curiosidades sobre os faraós do Egito Antigo',
      'Invenções acidentais que mudaram o mundo',
      'Recordes mundiais mais bizarros já registrados',
      'Fatos absurdos sobre o fundo do mar',
      'Mistérios da ciência que ainda não têm resposta',
    ],
    faqs: [
      {
        question: 'Vídeos de curiosidades realmente viralizam?',
        answer: 'Sim. O formato favorece retenção e compartilhamento, e os algoritmos de Shorts/Reels premiam conteúdo que segura o espectador — exatamente o que um bom gancho de curiosidade faz.',
      },
      {
        question: 'De onde vêm os fatos do roteiro?',
        answer: 'A IA gera o roteiro a partir do tema que você escreve. Recomendamos revisar os fatos antes de publicar, principalmente em temas técnicos — você tem controle total no editor.',
      },
      ...sharedFaq(),
    ],
  },
  {
    slug: 'religioso',
    label: 'Conteúdo Religioso',
    emoji: '🙏',
    accent: '#fbbf24',
    gradient: 'from-amber-900/40 to-yellow-900/30',
    recommendedTemplate: 'stock_narration',
    generateStyle: 'storytelling',
    metaTitle: 'Como Criar Vídeos Gospel e de Fé com IA | ClipIA',
    metaDescription:
      'Crie vídeos de mensagens de fé, reflexões e versículos para Shorts, Reels e TikTok. Narração em português e legendas automáticas. Comece grátis, sem cartão.',
    h1: 'Crie vídeos de fé e reflexão automaticamente',
    heroSubtitle: 'Leve mensagens que tocam o coração para milhares de pessoas, todos os dias.',
    intro:
      'O público brasileiro de conteúdo religioso é um dos maiores do mundo, e mensagens de fé estão entre as mais assistidas e compartilhadas em vídeo curto. Uma reflexão bem narrada, com a imagem certa e legenda no tempo da fala, pode alcançar e edificar milhares de pessoas.\n\nCom o ClipIA, você transforma uma mensagem, uma reflexão ou um versículo em um vídeo pronto. A IA estrutura a mensagem com começo, meio e chamado, gera a narração em português com tom acolhedor e monta o vídeo no formato vertical — ideal para alimentar um canal devocional com constância.\n\nPara conteúdo bíblico narrado de forma mais cinematográfica, você também pode usar o template de drama histórico, com imagens geradas por IA.',
    benefits: [
      { title: 'Tom que acolhe', description: 'Narração pausada e calorosa, no ritmo certo para reflexões e mensagens de fé.' },
      { title: 'Constância sem esforço', description: 'Publique uma mensagem por dia mantendo qualidade — a base de um canal devocional que cresce.' },
      { title: 'Imagens que transmitem paz', description: 'Mídia de fundo selecionada para o clima da mensagem; ou imagens geradas por IA para temas bíblicos.' },
      { title: 'Legenda no tempo da fala', description: 'Cada palavra aparece sincronizada, ajudando quem assiste sem som a acompanhar a mensagem.' },
    ],
    howItWorks: baseHowItWorks('Uma mensagem de fé para começar o dia com esperança'),
    exampleTopics: [
      'Uma mensagem de fé para começar o dia',
      'Reflexão sobre gratidão e as pequenas bênçãos',
      'Salmo 23: o Senhor é o meu pastor',
      'Como confiar em Deus nos momentos difíceis',
      'Uma oração curta para ter um dia abençoado',
      'O poder do perdão na sua vida',
      'Mensagem de esperança para quem está cansado',
      'Reflexão sobre fé e paciência',
      'Versículos para fortalecer a fé hoje',
      'Uma palavra de ânimo para a sua semana',
    ],
    faqs: [
      {
        question: 'Posso fazer vídeos com versículos da Bíblia?',
        answer: 'Sim. Você indica o versículo ou o tema no roteiro e o ClipIA monta a reflexão e a narração. Recomendamos revisar a citação antes de publicar para garantir fidelidade ao texto.',
      },
      {
        question: 'Dá para usar um tom mais cinematográfico para histórias bíblicas?',
        answer: 'Sim. O template de drama histórico narra a mensagem como um pequeno trailer, com imagens geradas por IA — ótimo para passagens e relatos bíblicos.',
      },
      ...sharedFaq(),
    ],
  },
  {
    slug: 'motivacional',
    label: 'Motivacional',
    emoji: '🔥',
    accent: '#fb923c',
    gradient: 'from-orange-900/40 to-red-900/30',
    recommendedTemplate: 'stock_narration',
    generateStyle: 'educational',
    metaTitle: 'Como Criar Vídeos Motivacionais com IA | ClipIA',
    metaDescription:
      'Crie vídeos motivacionais e de desenvolvimento pessoal para Shorts, Reels e TikTok em minutos. Narração em português e legendas automáticas. Comece grátis, sem cartão.',
    h1: 'Crie vídeos motivacionais automaticamente',
    heroSubtitle: 'Transforme uma ideia em uma mensagem que move pessoas a agir.',
    intro:
      'Conteúdo motivacional e de desenvolvimento pessoal tem audiência enorme e fiel. Frases sobre disciplina, foco e superação são salvas, compartilhadas e voltam a aparecer no feed — é um dos nichos que mais sustentam canais com publicações diárias.\n\nO ClipIA transforma um tema (como "a disciplina vence a motivação") em um vídeo curto com narração firme, legendas de impacto e mídia que reforça a mensagem. Você mantém a constância de postagem que o algoritmo recompensa, sem passar horas editando.\n\nIdeal para criadores de desenvolvimento pessoal, coaches e canais de alta performance que precisam de volume sem abrir mão da qualidade.',
    benefits: [
      { title: 'Mensagem de impacto', description: 'Roteiro direto, com frases que ficam na cabeça e convidam à ação.' },
      { title: 'Narração com energia', description: 'Voz firme e ritmada, no tom certo para mensagens de superação e disciplina.' },
      { title: 'Legendas de impacto', description: 'Estilos de legenda que destacam as palavras-chave e aumentam o tempo de tela.' },
      { title: 'Volume diário sem esforço', description: 'Produza vários vídeos por semana e mantenha o canal sempre ativo.' },
    ],
    howItWorks: baseHowItWorks('A disciplina te leva mais longe que a motivação'),
    exampleTopics: [
      'A disciplina vence a motivação todos os dias',
      '3 hábitos das pessoas de alta performance',
      'Como parar de procrastinar de uma vez',
      'O segredo da consistência que ninguém conta',
      'Por que sair da zona de conforto muda tudo',
      'Como acordar cedo e dominar a sua manhã',
      'O poder de não desistir no momento difícil',
      'Foco: como fazer mais em menos tempo',
      'Mentalidade de crescimento na prática',
      'A regra dos 5 segundos para agir agora',
    ],
    faqs: [
      {
        question: 'Consigo manter uma identidade visual no canal?',
        answer: 'Sim. Você define o estilo de legenda, as cores e a voz no editor, mantendo uma assinatura visual consistente entre os vídeos.',
      },
      {
        question: 'Serve para canais de desenvolvimento pessoal e coaching?',
        answer: 'Perfeitamente. O nicho motivacional é um dos que mais se beneficiam de volume e constância, e o ClipIA foi feito para entregar exatamente isso.',
      },
      ...sharedFaq(),
    ],
  },
  {
    slug: 'financas',
    label: 'Finanças',
    emoji: '💰',
    accent: '#34d399',
    gradient: 'from-emerald-900/40 to-green-900/30',
    recommendedTemplate: 'stock_narration',
    generateStyle: 'educational',
    metaTitle: 'Como Criar Vídeos de Educação Financeira com IA | ClipIA',
    metaDescription:
      'Crie vídeos de educação financeira e dicas de dinheiro para Shorts, Reels e TikTok em minutos. Narração em português e legendas automáticas. Comece grátis, sem cartão.',
    h1: 'Crie vídeos de educação financeira automaticamente',
    heroSubtitle: 'Explique dinheiro de um jeito simples e construa uma audiência que confia em você.',
    intro:
      'Educação financeira é um dos nichos mais valiosos do vídeo curto: a audiência tem alta intenção, engaja com dicas práticas e atrai oportunidades de monetização acima da média. Conteúdo sobre economizar, organizar as contas e sair das dívidas é buscado o ano inteiro.\n\nO ClipIA transforma um tema (como "3 formas de economizar sem perceber") em um vídeo claro e objetivo, com narração em português, legendas sincronizadas e mídia que ilustra a mensagem. Você publica com frequência e constrói autoridade no assunto, sem gastar horas editando.\n\nObservação: o conteúdo é informativo e educativo. Evite recomendações específicas de investimento — foque em educação e bons hábitos financeiros.',
    benefits: [
      { title: 'Didática que prende', description: 'A IA quebra conceitos de dinheiro em frases simples e exemplos do dia a dia.' },
      { title: 'Audiência de alto valor', description: 'O público de finanças tem alta intenção e atrai melhores oportunidades de monetização.' },
      { title: 'Constância gera autoridade', description: 'Publique com frequência e torne-se referência no seu tema financeiro.' },
      { title: 'Visual limpo e profissional', description: 'Mídia e legendas que passam credibilidade, essenciais para o nicho.' },
    ],
    howItWorks: baseHowItWorks('3 formas de economizar dinheiro sem perceber'),
    exampleTopics: [
      '3 formas de economizar dinheiro sem perceber',
      'Como sair das dívidas em 5 passos',
      'O método 50-30-20 para organizar o salário',
      'Erros que mantêm você sempre sem dinheiro',
      'Como montar uma reserva de emergência',
      'Hábitos de quem consegue guardar dinheiro',
      'O que ninguém te ensina sobre cartão de crédito',
      'Como gastar menos no supermercado',
      'Pequenos gastos que somam uma fortuna no ano',
      'Como começar a investir sabendo do zero',
    ],
    faqs: [
      {
        question: 'O conteúdo serve como recomendação de investimento?',
        answer: 'Não. Os vídeos são educativos e informativos. Para temas de investimento, mantenha o conteúdo geral e educacional, sem indicar produtos específicos.',
      },
      {
        question: 'Funciona para quem está começando um canal de finanças?',
        answer: 'Sim. É ideal para quem quer publicar com frequência e construir autoridade, sem precisar editar cada vídeo manualmente.',
      },
      ...sharedFaq(),
    ],
  },
  {
    slug: 'historias',
    label: 'Histórias & Mistério',
    emoji: '📖',
    accent: '#3e9bff',
    gradient: 'from-blue-900/40 to-indigo-950/40',
    recommendedTemplate: 'story_time',
    generateStyle: 'storytelling',
    metaTitle: 'Como Criar Vídeos de Histórias e Mistério com IA | ClipIA',
    metaDescription:
      'Crie vídeos de histórias, casos reais e mistérios para Shorts, Reels e TikTok. Narração envolvente em português e legendas automáticas. Comece grátis, sem cartão.',
    h1: 'Crie vídeos de histórias e mistério automaticamente',
    heroSubtitle: 'Narrativas que prendem do começo ao fim — o formato campeão de tempo de tela.',
    intro:
      'Histórias narradas dominam o vídeo curto quando o assunto é tempo de tela. Casos reais, mistérios não resolvidos e relatos com reviravolta seguram o espectador até a última palavra para descobrir o que aconteceu — e o algoritmo adora isso.\n\nO ClipIA monta a narrativa com tensão e suspense, revela a informação aos poucos e narra em português no ritmo certo, com fundo no estilo "story time" para manter os olhos na tela. Você só dá o tema e o vídeo sai pronto, com legendas sincronizadas.\n\nPerfeito para canais de histórias, casos reais, mistérios e relatos — um dos formatos faceless mais consistentes para crescer.',
    benefits: [
      { title: 'Tempo de tela alto', description: 'A estrutura cria tensão e segura o espectador até o desfecho da história.' },
      { title: 'Narração envolvente', description: 'Voz no ritmo de quem conta um bom causo, com pausas que criam suspense.' },
      { title: 'Fundo que não distrai', description: 'Estilo "story time" com fundo dinâmico que mantém a atenção sem competir com a narração.' },
      { title: 'Formato faceless', description: 'Não precisa aparecer: a história e a narração são as estrelas do vídeo.' },
    ],
    howItWorks: baseHowItWorks('O mistério do navio que sumiu sem deixar rastros'),
    exampleTopics: [
      'O mistério do navio encontrado sem tripulação',
      'O caso real que a polícia nunca conseguiu explicar',
      'A história por trás do lugar mais assustador do mundo',
      'Desaparecimentos que continuam sem solução',
      'A lenda urbana que acabou sendo verdade',
      'O golpe mais inteligente já aplicado na história',
      'Uma viagem que terminou de forma inesperada',
      'O segredo escondido de uma cidade abandonada',
      'Coincidências históricas que parecem impossíveis',
      'A descoberta que mudou tudo no último minuto',
    ],
    faqs: [
      {
        question: 'As histórias são reais ou ficção?',
        answer: 'Você decide pelo tema. Para casos reais, recomendamos revisar os fatos antes de publicar. Para histórias de ficção ou lendas, deixe claro o caráter narrativo do conteúdo.',
      },
      {
        question: 'Por que esse nicho tem tanto tempo de tela?',
        answer: 'Porque a narrativa cria uma pergunta na cabeça do espectador logo no início e só responde no fim — o que o mantém assistindo, sinal que os algoritmos premiam.',
      },
      ...sharedFaq(),
    ],
  },
  {
    slug: 'humor',
    label: 'Humor',
    emoji: '😂',
    accent: '#ff7a61',
    gradient: 'from-orange-900/40 to-rose-900/30',
    recommendedTemplate: 'character_narration',
    generateStyle: 'comedy',
    metaTitle: 'Como Criar Vídeos Engraçados com IA | ClipIA',
    metaDescription:
      'Crie vídeos engraçados com personagem narrador para Shorts, Reels e TikTok. Humor automático, narração em português e legendas. Comece grátis, sem cartão.',
    h1: 'Crie vídeos engraçados automaticamente',
    heroSubtitle: 'Um personagem narrando fatos absurdos com aquele tom cômico que viraliza.',
    intro:
      'Humor é combustível de viralização. Vídeos engraçados são compartilhados em conversas, salvos para rir de novo e alcançam pessoas muito além dos seus seguidores. Mas escrever piada e editar com timing cômico dá trabalho.\n\nO ClipIA usa um personagem narrador com tom cômico e informal para apresentar fatos absurdos e curiosidades de um jeito divertido. A IA escreve com exageros e comparações engraçadas, gera a narração e monta o vídeo — você só escolhe o tema e dá boas risadas no resultado.\n\nÉ o diferencial para um canal que quer se destacar pela personalidade, com aquele formato de "narrador maluco" que o público já ama.',
    benefits: [
      { title: 'Personagem com personalidade', description: 'Um narrador cômico dá identidade ao canal e faz o público voltar pelo estilo.' },
      { title: 'Roteiro com timing de piada', description: 'A IA escreve com exageros, ganchos e comparações absurdas — no ritmo da comédia.' },
      { title: 'Alto potencial de compartilhamento', description: 'Conteúdo engraçado é compartilhado em conversas, multiplicando o alcance organicamente.' },
      { title: 'Fácil de manter', description: 'Produza vários vídeos por semana sem precisar bolar e editar cada piada do zero.' },
    ],
    howItWorks: baseHowItWorks('Os animais mais sem noção da natureza'),
    exampleTopics: [
      'Os animais mais sem noção da natureza',
      'Invenções inúteis que existem de verdade',
      'Fatos absurdos que parecem piada mas são reais',
      'As leis mais ridículas que já existiram',
      'Coisas que só fazem sentido no Brasil',
      'Os perrengues mais épicos da história',
      'Recordes mundiais que ninguém pediu',
      'Situações constrangedoras que todo mundo já viveu',
      'As desculpas mais criativas já inventadas',
      'Produtos esquisitos que realmente foram vendidos',
    ],
    faqs: [
      {
        question: 'Como funciona o personagem narrador?',
        answer: 'O template de personagem usa um narrador com tom cômico e informal por cima de um fundo dinâmico. A narração tem humor, exageros e ritmo de piada, dando uma cara única ao canal.',
      },
      {
        question: 'Posso ajustar o nível de humor?',
        answer: 'Sim. Você refina o roteiro e a narração no editor antes de exportar — dá para deixar mais leve ou mais escrachado conforme o seu público.',
      },
      ...sharedFaq(),
    ],
  },
  {
    slug: 'drama',
    label: 'Drama Histórico',
    emoji: '🎭',
    accent: '#f87171',
    gradient: 'from-red-900/40 to-rose-950/40',
    recommendedTemplate: 'novelinha_historica',
    generateStyle: 'storytelling',
    metaTitle: 'Como Criar Vídeos de História com IA Cinematográfica | ClipIA',
    metaDescription:
      'Crie vídeos de fatos históricos narrados como trailer cinematográfico, com imagens geradas por IA. Para Shorts, Reels e TikTok. Comece grátis, sem cartão.',
    h1: 'Crie vídeos de drama histórico automaticamente',
    heroSubtitle: 'Fatos reais narrados como um trailer de cinema, com imagens geradas por IA.',
    intro:
      'Imagine contar um fato histórico curioso, macabro ou pouco conhecido com a gravidade de um trailer de cinema — narração teatral, imagens dramáticas e uma reviravolta no final. Esse é o formato de drama histórico, um dos mais impressionantes para vídeo curto e o que mais demonstra o que a IA é capaz de criar.\n\nO ClipIA usa imagens geradas por inteligência artificial (gpt-image) e uma narração grave e pausada para transformar um evento real em um curta cinematográfico vertical. Cada cena é construída com gancho, contexto, clímax e desfecho — sem você precisar de banco de imagens nem de software de edição.\n\nÉ o template premium da plataforma: ideal para canais de história, fatos sombrios e relatos bíblicos narrados de forma épica.',
    benefits: [
      { title: 'Imagens exclusivas por IA', description: 'Cada cena é gerada sob medida para o roteiro — nada de banco de imagens repetido.' },
      { title: 'Narração de documentário', description: 'Voz grave, pausada e teatral, no clima de um trailer cinematográfico.' },
      { title: 'Arco narrativo completo', description: 'Gancho, contexto, clímax e reviravolta em poucos segundos, prendendo até o fim.' },
      { title: 'Efeito "uau" que gera autoridade', description: 'O acabamento cinematográfico diferencia o seu canal e impressiona quem assiste.' },
    ],
    howItWorks: baseHowItWorks('O fato histórico macabro que quase ninguém conhece'),
    exampleTopics: [
      'O fato histórico macabro que quase ninguém conhece',
      'A tragédia esquecida que mudou um país',
      'O império que desapareceu da noite para o dia',
      'A descoberta que custou a vida de quem a fez',
      'O segredo levado para o túmulo por um rei',
      'A batalha decidida por um único erro',
      'A epidemia que reescreveu a história da humanidade',
      'O artefato amaldiçoado que ninguém explica',
      'A história real por trás de uma lenda famosa',
      'O dia em que o mundo quase acabou',
    ],
    faqs: [
      {
        question: 'Como as imagens são criadas?',
        answer: 'Por inteligência artificial (gpt-image). Para cada cena do roteiro, o ClipIA gera uma imagem cinematográfica original em formato vertical, sem precisar de banco de imagens.',
      },
      {
        question: 'Esse template custa mais créditos?',
        answer: 'Sim. Por usar geração de imagens por IA, o drama histórico consome mais créditos que os templates com mídia de stock. É o formato premium da plataforma.',
      },
      ...sharedFaq(),
    ],
  },
]

export function getAllNicheSlugs(): string[] {
  return NICHES.map((n) => n.slug)
}

export function getNicheBySlug(slug: string): NicheContent | undefined {
  return NICHES.find((n) => n.slug === slug)
}
