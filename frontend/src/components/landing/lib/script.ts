// Illustrative script generator for the interactive demo.
// This only produces plausible pt-BR scaffolding text — real generation happens
// after creating an account. See the disclaimer in the demo section.

import type { Accent } from "./data";

export interface Scene {
  caption: string; // short on-screen label
  narration: string; // full voiceover line (used as word-by-word caption preview)
  // Visual hints for procedural thumbnails (optional; default applied by consumers).
  accent?: Accent;
  icon?: string;
}

export interface GeneratedScript {
  hook: string;
  scenes: Scene[];
  credits: number;
  voiceCredits: number;
  durationLabel: string;
}

const TEMPLATES: Record<
  string,
  { hook: (t: string) => string; pool: Scene[] }
> = {
  curiosidades: {
    hook: (t) => `${t} que parecem mentira`,
    pool: [
      { caption: "PARECIA IMPOSSÍVEL", narration: "A primeira curiosidade sobre isso surpreende até quem já estudou o assunto.", accent: "azure", icon: "planet" },
      { caption: "NINGUÉM CONTA", narration: "A segunda vai mudar a forma como você enxerga isso no dia a dia.", accent: "coral", icon: "star" },
      { caption: "A MAIOR SURPRESA", narration: "E a última é tão impressionante que vale o vídeo inteiro.", accent: "mint", icon: "galaxy" },
      { caption: "POR ISSO IMPORTA", narration: "É exatamente esse tipo de detalhe que prende a atenção desde o início.", accent: "azure", icon: "blackhole" },
      { caption: "CONFIRA AGORA", narration: "Fica até o final, porque a melhor curiosidade ainda está por vir.", accent: "coral", icon: "rocket" },
      { caption: "COMENTA AÍ", narration: "Qual dessas você já conhecia? Conta nos comentários.", accent: "mint", icon: "satellite" },
    ],
  },
  motivacional: {
    hook: (t) => `${t}: o que ninguém te disse sobre recomeçar`,
    pool: [
      { caption: "O PRIMEIRO PASSO", narration: "Tudo começa quando você decide que isso vale a tentativa." },
      { caption: "SEM DESCULPAS", narration: "Não existe momento perfeito para começar a mudar." },
      { caption: "UM DIA DE CADA VEZ", narration: "Pequenos passos consistentes vencem a motivação que some." },
      { caption: "VOCÊ CONSEGUE", narration: "O seu esforço de hoje constrói o resultado de amanhã." },
      { caption: "NÃO PARE", narration: "A diferença está em continuar quando fica difícil." },
      { caption: "ATÉ A PRÓXIMA", narration: "Salva esse vídeo para quando você precisar lembrar." },
    ],
  },
  financas: {
    hook: (t) => `${t}: 3 atitudes que mudam o seu bolso`,
    pool: [
      { caption: "PARE O SANGRAMENTO", narration: "Antes de investir, entenda para onde o seu dinheiro está indo." },
      { caption: "PAGUE-SE PRIMEIRO", narration: "Separe uma parte da renda antes de qualquer outro gasto." },
      { caption: "JUROS COMPÕEM", narration: "No longo prazo, a constância vence o valor alto." },
      { caption: "O HÁBITO VENCE", narration: "Decisões pequenas e repetidas constroem a liberdade financeira." },
      { caption: "FUJA DAS ARMADILHAS", narration: "Cuidado com as dívidas que parecem soluções rápidas." },
      { caption: "COMENTE", narration: "Qual dessas atitudes você já pratica? Deixa nos comentários." },
    ],
  },
  misterio: {
    hook: (t) => `${t}: o mistério que intriga até hoje`,
    pool: [
      { caption: "TUDO COMEÇOU", narration: "No começo, parecia um caso comum sobre o assunto." },
      { caption: "SEM EXPLICAÇÃO", narration: "Mas os detalhes não batiam com nenhuma teoria." },
      { caption: "TESTEMUNHAS", narration: "Quem esteve lá jamais esqueceu o que viu." },
      { caption: "SEM RESPOSTA", narration: "Até hoje, ninguém conseguiu explicar o que realmente aconteceu." },
      { caption: "AINDA HOJE", narration: "Novos detalhes aparecem e só aumentam a dúvida." },
      { caption: "COMENTE A TEORIA", narration: "Qual a sua teoria? Conta para a gente nos comentários." },
    ],
  },
  religioso: {
    hook: (t) => `${t}: uma mensagem para o seu dia`,
    pool: [
      { caption: "FÉ QUE MOVE", narration: "Comece o dia lembrando que a fé remove montanhas." },
      { caption: "NÃO DESISTA", narration: "Mesmo no deserto, há uma promessa cuidando de você." },
      { caption: "DEUS NO CONTROLE", narration: "Entregue suas preocupações e siga em paz." },
      { caption: "GRAÇA RENOVA", narration: "A cada manhã, há uma nova chance de recomeçar." },
      { caption: "SEJA LUZ", narration: "Leve essa palavra para quem precisa ouvir hoje." },
      { caption: "AMÉM", narration: "Compartilhe essa mensagem com alguém especial." },
    ],
  },
  humor: {
    hook: (t) => `${t}: a parte que ninguém admite`,
    pool: [
      { caption: "TODO MUNDO PASSA", narration: "A gente promete que não vai acontecer de novo." },
      { caption: "ERA SÓ UMA VEZ", narration: "Mas aí aparece aquela situação impossível." },
      { caption: "AQUELE AMIGO", narration: "E sempre tem alguém para piorar a situação." },
      { caption: "PLANO B", narration: "Quando tudo dá errado, o jeito é rir da própria cara." },
      { caption: "NÃO ERA PRA SER", narration: "Era para ser simples, virou história para contar." },
      { caption: "RIR CURA", narration: "No fim, dá para rir disso. Quase tudo." },
    ],
  },
  drama: {
    hook: (t) => `${t}: a história que o tempo quase apagou`,
    pool: [
      { caption: "ERA OUTRO TEMPO", narration: "Há séculos, esse assunto movia impérios e destinos." },
      { caption: "PODER E GUERRA", narration: "As decisões de poucos mudaram o rumo de muitos." },
      { caption: "A QUEDA", narration: "Nenhum poder dura para sempre, por maior que pareça." },
      { caption: "O LEGADO", narration: "O que sobrou hoje vive em ruínas e em histórias." },
      { caption: "LIÇÃO", narration: "E o passado ainda ensina quem sabe ouvir." },
      { caption: "COMENTE", narration: "Você conhecia essa história? Conta nos comentários." },
    ],
  },
};

const DEFAULT_THEME: Record<string, string> = {
  curiosidades: "3 curiosidades sobre o espaço",
  motivacional: "Recomeçar depois de uma derrota",
  financas: "Sair das dívidas",
  misterio: "O navio que desapareceu",
  religioso: "Começar o dia com fé",
  humor: "Segunda-feira às 7h da manhã",
  drama: "A queda de um império",
};

const DURATION_TO_SCENES: Record<number, number> = { 15: 3, 30: 4, 60: 6 };

function clean(t: string): string {
  const v = t.trim();
  return v.length ? v.charAt(0).toUpperCase() + v.slice(1) : "";
}

export function generateScript(
  themeRaw: string,
  nicheId: string,
  duration: number,
  voiceCredits: number
): GeneratedScript {
  const tpl = TEMPLATES[nicheId] ?? TEMPLATES.curiosidades;
  const theme = clean(themeRaw) || DEFAULT_THEME[nicheId] || DEFAULT_THEME.curiosidades;
  const count = DURATION_TO_SCENES[duration] ?? 4;
  const scenes = tpl.pool.slice(0, count);
  return {
    hook: tpl.hook(theme),
    scenes,
    credits: voiceCredits,
    voiceCredits,
    durationLabel: `${duration}s`,
  };
}

export const HERO_SCRIPT = generateScript(
  "3 curiosidades sobre o espaço",
  "curiosidades",
  30,
  1
);
