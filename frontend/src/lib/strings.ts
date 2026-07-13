export const strings = {
  // Auth
  auth: {
    login: {
      title: "Entrar",
      email: "Email",
      password: "Senha",
      submit: "Entrar",
      loading: "Entrando...",
      noAccount: "Não tem conta?",
      register: "Criar conta",
      forgotPassword: "Esqueci minha senha",
      error: "Email ou senha incorretos",
    },
    register: {
      title: "Crie sua conta",
      subtitle: "Comece com 2 créditos grátis — até 2 vídeos com voz padrão. Sem cartão.",
      name: "Nome",
      email: "Email",
      password: "Senha",
      passwordPlaceholder: "Mínimo 6 caracteres",
      submit: "Criar conta grátis",
      loading: "Criando conta...",
      hasAccount: "Já tem conta?",
      login: "Entrar",
    },
    verify: {
      title: "Verifique seu email",
      subtitle: (email: string) => `Enviamos um código de 6 dígitos para ${email}`,
      submit: "Verificar email",
      loading: "Verificando...",
      resend: "Reenviar código",
      resending: "Reenviando...",
      resendCooldown: (seconds: number) => `Reenviar código em ${seconds}s`,
      errorIncomplete: "Digite o código completo de 6 dígitos",
    },
    // ... forgot-password, reset-password
  },

  // Dashboard
  dashboard: {
    generate: {
      title: "Gerar novo vídeo",
      topicLabel: "Sobre o que será o vídeo?",
      topicPlaceholder: "Ex: 5 curiosidades sobre o oceano",
      submit: "Gerar vídeo",
      loading: "Gerando...",
      verifyFirst: "Verifique seu email antes de gerar vídeos",
      noCredits: "Créditos insuficientes",
    },
    videos: {
      title: "Seus vídeos",
      empty: "Nenhum vídeo ainda. Gere seu primeiro!",
      edit: "Editar",
      download: "Baixar",
    },
    credits: {
      title: "Créditos",
      balance: (n: number) => `${n} crédito${n !== 1 ? 's' : ''}`,
      buy: "Comprar créditos",
    },
    verifyBanner: {
      title: "Verifique seu email",
      description: "Confirme seu email para receber seus créditos de boas-vindas e começar a gerar vídeos.",
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
    network: "Sem conexão com o servidor.",
    sessionExpired: "Sua sessão expirou. Faça login novamente.",
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
