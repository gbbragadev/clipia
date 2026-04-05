export const strings = {
  // Auth
  auth: {
    login: {
      title: "Entrar",
      email: "Email",
      password: "Senha",
      submit: "Entrar",
      loading: "Entrando...",
      noAccount: "Nao tem conta?",
      register: "Criar conta",
      forgotPassword: "Esqueci minha senha",
      error: "Email ou senha incorretos",
    },
    register: {
      title: "Crie sua conta",
      subtitle: "Verifique seu email e ganhe 2 creditos gratis",
      name: "Nome",
      email: "Email",
      password: "Senha",
      passwordPlaceholder: "Minimo 6 caracteres",
      submit: "Criar conta gratis",
      loading: "Criando conta...",
      hasAccount: "Ja tem conta?",
      login: "Entrar",
    },
    verify: {
      title: "Verifique seu email",
      subtitle: (email: string) => `Enviamos um codigo de 6 digitos para ${email}`,
      submit: "Verificar email",
      loading: "Verificando...",
      resend: "Reenviar codigo",
      resending: "Reenviando...",
      resendCooldown: (seconds: number) => `Reenviar codigo em ${seconds}s`,
      errorIncomplete: "Digite o codigo completo de 6 digitos",
    },
    // ... forgot-password, reset-password
  },

  // Dashboard
  dashboard: {
    generate: {
      title: "Gerar novo video",
      topicLabel: "Sobre o que sera o video?",
      topicPlaceholder: "Ex: 5 curiosidades sobre o oceano",
      submit: "Gerar video",
      loading: "Gerando...",
      verifyFirst: "Verifique seu email antes de gerar videos",
      noCredits: "Creditos insuficientes",
    },
    videos: {
      title: "Seus videos",
      empty: "Nenhum video ainda. Gere seu primeiro!",
      edit: "Editar",
      download: "Baixar",
    },
    credits: {
      title: "Creditos",
      balance: (n: number) => `${n} credito${n !== 1 ? 's' : ''}`,
      buy: "Comprar creditos",
    },
    verifyBanner: {
      title: "Verifique seu email",
      description: "Confirme seu email para receber 2 creditos gratis e comecar a gerar videos.",
      cta: "Verificar agora",
    },
  },

  // Editor
  editor: {
    scenes: "Cenas",
    voice: "Voz",
    subtitles: "Legendas",
    elements: "Elementos",
    ai: "IA",
    export: "Exportar",
    saving: "Salvando...",
    saved: "Salvo",
  },

  // Errors
  errors: {
    generic: "Algo deu errado. Tente novamente.",
    network: "Sem conexao com o servidor.",
    sessionExpired: "Sua sessao expirou. Faca login novamente.",
    rateLimit: "Muitas tentativas. Aguarde um momento.",
  },

  // Common
  common: {
    loading: "Carregando...",
    cancel: "Cancelar",
    save: "Salvar",
    delete: "Excluir",
    confirm: "Confirmar",
    back: "Voltar",
  },
} as const;

export type Strings = typeof strings;
