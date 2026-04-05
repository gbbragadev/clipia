# ClipIA — Tarefas para Gemini

Cada secao e uma tarefa independente. Copie e cole como prompt separado.

---

## TAREFA 1: SEO + Meta Tags + Sitemap

### Contexto
ClipIA e uma plataforma SaaS brasileira de geracao automatizada de videos curtos com IA.
Dominio: clipia.com.br | Stack: Next.js 16 + React 19 | Idioma: pt-BR

### Paginas existentes
```
/ — Landing page (hero, showcase, demo, how it works, waitlist, footer)
/auth/login — Login
/auth/register — Criar conta
/auth/verify — Verificar email (OTP)
/auth/forgot-password — Esqueci senha
/auth/reset-password — Redefinir senha
/dashboard — Painel (gerar videos, lista de jobs)
/dashboard/credits — Comprar creditos, historico
/editor/[jobId] — Editor de video com Remotion
```

### Layout.tsx atual (ja tem OG basico)
```tsx
export const metadata: Metadata = {
  title: "ClipIA - Crie videos curtos com IA",
  description: "Transforme qualquer tema em video pronto para publicar. Roteiro, narracao, legendas e edicao — tudo automatico com IA.",
  openGraph: {
    title: "ClipIA - Crie videos curtos com IA",
    description: "Transforme qualquer tema em video pronto para publicar...",
    url: "https://clipia.com.br",
    siteName: "ClipIA",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "ClipIA" }],
    locale: "pt_BR",
    type: "website",
  },
  twitter: { card: "summary_large_image", ... },
  metadataBase: new URL("https://clipia.com.br"),
};
```

### O que criar

#### 1. Meta tags por pagina
Criar metadata export em cada page.tsx com titulo e descricao unicos. Exemplos:
- `/auth/login` → title: "Entrar | ClipIA", description: "Acesse sua conta ClipIA e comece a criar videos curtos com IA."
- `/auth/register` → title: "Criar conta | ClipIA", description: "Crie sua conta gratis e ganhe 2 creditos para gerar seus primeiros videos com IA."
- `/dashboard` → title: "Dashboard | ClipIA", description: "Gere e gerencie seus videos curtos com IA."
- `/dashboard/credits` → title: "Creditos | ClipIA", description: "Compre creditos para gerar mais videos com IA."

Para cada pagina, gerar titulo (max 60 chars) e descricao (max 155 chars) otimizados para SEO em pt-BR.

#### 2. sitemap.ts (Next.js App Router dynamic sitemap)
Criar `frontend/src/app/sitemap.ts`:
```typescript
import type { MetadataRoute } from 'next'

export default function sitemap(): MetadataRoute.Sitemap {
  return [
    { url: 'https://clipia.com.br', lastModified: new Date(), changeFrequency: 'weekly', priority: 1 },
    { url: 'https://clipia.com.br/auth/login', lastModified: new Date(), changeFrequency: 'monthly', priority: 0.5 },
    { url: 'https://clipia.com.br/auth/register', lastModified: new Date(), changeFrequency: 'monthly', priority: 0.7 },
    // ... demais paginas publicas (NAO incluir dashboard, editor, verify)
  ]
}
```

#### 3. robots.ts
Criar `frontend/src/app/robots.ts`:
```typescript
import type { MetadataRoute } from 'next'

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: '*',
      allow: '/',
      disallow: ['/dashboard/', '/editor/', '/api/', '/auth/verify', '/auth/reset-password'],
    },
    sitemap: 'https://clipia.com.br/sitemap.xml',
  }
}
```

#### 4. Structured Data (JSON-LD)
Adicionar no layout.tsx ou na landing page:
```json
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "ClipIA",
  "applicationCategory": "MultimediaApplication",
  "operatingSystem": "Web",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "BRL"
  },
  "description": "Plataforma de geracao automatizada de videos curtos com IA",
  "url": "https://clipia.com.br"
}
```

#### Verificacao
```bash
cd frontend && npx tsc --noEmit
```
Testar: `curl https://clipia.com.br/sitemap.xml` e `curl https://clipia.com.br/robots.txt`

---

## TAREFA 2: Copy e Microcopy da UI

### Contexto
ClipIA e um SaaS brasileiro. Todo texto da UI deve ser em pt-BR natural, consistente, e amigavel. Algumas areas tem texto hardcoded em ingles ou inconsistente.

### Diretrizes de voz
- Tom: profissional mas acessivel, sem ser informal demais
- Usar "voce" (nao "tu")
- Evitar jargao tecnico para o usuario final
- Mensagens de erro: claras e com acao sugerida ("Tente novamente" em vez de "Error 500")
- Botoes: acao clara no imperativo ("Criar conta" nao "Submit")
- Acentos e cedilha corretos sempre

### Varredura completa
Leia TODOS os arquivos .tsx em `frontend/src/` e produza um relatorio com:

1. **Textos em ingles** que deveriam estar em portugues (ex: "Job not found", "Error", "Loading")
2. **Inconsistencias** (ex: "creditos" vs "créditos", "video" vs "vídeo")
3. **Mensagens de erro genericas** que poderiam ser mais uteis
4. **Placeholders vazios ou genericos** (ex: "Digite aqui...")
5. **Botoes com texto fraco** (ex: "OK", "Submit", "Enviar")
6. **Tooltip/aria-label ausentes** em icones e botoes com so icone

### Formato do relatorio
Para cada item encontrado:
```
ARQUIVO: src/components/dashboard/GenerateForm.tsx
LINHA: ~45
ATUAL: "Loading..."
SUGERIDO: "Gerando seu video..."
MOTIVO: Texto em ingles, deveria ser pt-BR com contexto
```

### Depois do relatorio
Aplicar TODAS as correcoes encontradas diretamente nos arquivos. Nao apenas reportar — corrigir.

### Verificacao
```bash
cd frontend && npx tsc --noEmit
# Buscar textos em ingles remanescentes:
grep -rn "Loading\|Error\|Submit\|Cancel\|Delete\|Success\|Failed\|not found" frontend/src/ --include="*.tsx" | grep -v node_modules | grep -v ".d.ts"
```

---

## TAREFA 3: Documentacao de API (OpenAPI)

### Contexto
Backend FastAPI em `app/`. Os endpoints tem pouca ou nenhuma documentacao. FastAPI gera Swagger automatico em `/docs`, mas os descriptions estao vazios ou genericos.

### Endpoints existentes (todos sob /api/v1/)
```
Auth:
  POST /auth/register — Criar conta (retorna JWT, envia OTP)
  POST /auth/login — Login (retorna JWT)
  POST /auth/verify-email — Verificar email com OTP
  POST /auth/resend-code — Reenviar codigo OTP
  POST /auth/forgot-password — Solicitar reset de senha
  POST /auth/verify-reset-code — Verificar codigo de reset
  POST /auth/reset-password — Redefinir senha com token
  GET  /auth/me — Dados do usuario autenticado

Videos:
  POST /generate — Gerar video (1 credito)
  GET  /jobs/{job_id} — Status do job
  GET  /jobs/{job_id}/status — Status rapido (polling)
  GET  /jobs — Lista de jobs do usuario
  GET  /jobs/{job_id}/download — Download do video MP4
  GET  /jobs/{job_id}/composition — Dados do editor Remotion
  POST /jobs/{job_id}/edit — Salvar estado do editor
  POST /jobs/{job_id}/regenerate-tts — Regerar narracao
  POST /jobs/{job_id}/ai-suggest — Sugestao IA (0.5 credito)
  POST /jobs/{job_id}/render — Re-render com edicoes
  POST /jobs/{job_id}/reset — Resetar job (1 credito)

Pagamentos:
  GET  /credits/packages — Listar pacotes de creditos
  POST /credits/checkout — Criar checkout MercadoPago
  GET  /credits/history — Historico de compras
  POST /webhooks/mercadopago — Webhook MercadoPago

Outros:
  GET  /templates — Templates de video disponiveis
  POST /waitlist — Entrar na waitlist
  GET  /health — Health check
  GET  /admin/storage-stats — Estatisticas de storage
```

### O que fazer

Para CADA endpoint, adicionar nos arquivos de rotas:

1. **Docstring rica** na funcao do endpoint:
```python
@router.post("/generate", summary="Gerar video curto", tags=["Videos"])
async def generate(...):
    """
    Cria um novo video curto a partir de um tema.

    - Debita 1 credito do usuario
    - Requer email verificado
    - Inicia pipeline assincrono (Celery)
    - Retorna job_id para polling de status

    **Rate limit**: 10 requests/minuto
    """
```

2. **Response models** documentados com `responses={}`:
```python
@router.post("/generate",
    summary="Gerar video curto",
    responses={
        200: {"description": "Job criado com sucesso"},
        402: {"description": "Creditos insuficientes"},
        403: {"description": "Email nao verificado"},
        429: {"description": "Rate limit excedido"},
    }
)
```

3. **Field descriptions** nos schemas Pydantic:
```python
class GenerateRequest(BaseModel):
    topic: str = Field(..., min_length=10, max_length=500, description="Tema do video. Ex: '5 curiosidades sobre o oceano'")
    style: str = Field(..., description="Estilo da narracao: educational, storytelling, news, comedy")
    duration_target: int = Field(..., ge=15, le=180, description="Duracao alvo em segundos (15-180)")
    template_id: str = Field("stock_narration", description="Template de video: stock_narration, gameplay, character, story")
```

4. **Tags organizadas** no FastAPI app:
```python
app = FastAPI(
    title="ClipIA API",
    version="0.1.0",
    description="API para geracao automatizada de videos curtos com IA",
    openapi_tags=[
        {"name": "Auth", "description": "Autenticacao e gerenciamento de conta"},
        {"name": "Videos", "description": "Geracao e edicao de videos"},
        {"name": "Pagamentos", "description": "Creditos e checkout MercadoPago"},
        {"name": "Admin", "description": "Endpoints administrativos"},
    ]
)
```

### Verificacao
```bash
cd /home/gui/projects/auto-shorts && source .venv/bin/activate
python -c "from app.main import app; import json; print(json.dumps(app.openapi(), indent=2))" | head -50
pytest tests/ -q
```
Acessar: http://localhost:8005/docs — verificar que Swagger esta bonito e completo.

---

## TAREFA 4: Termos de Uso + Politica de Privacidade

### Contexto
ClipIA e um SaaS brasileiro. Dominio: clipia.com.br. Empresa: Braga Consultoria (CNPJ 65.620.439/0001-62), Cafelendia-PR.

O app coleta: email, nome, senha (hash), historico de videos gerados, dados de pagamento (via MercadoPago, nao armazenamos cartao), IP para rate limiting.

Usa cookies: apenas localStorage para JWT token (nao usa cookies tradicionais).

Integrancoes externas: Anthropic (Claude API para roteiros), Microsoft Edge TTS (narracao), Pexels (video stock), MercadoPago (pagamentos), Gmail SMTP (emails transacionais).

### O que criar

#### 1. Pagina /termos — Termos de Uso
Criar `frontend/src/app/termos/page.tsx` com:
- Termos de servico completos em pt-BR
- Cobrir: descricao do servico, cadastro, creditos (nao reembolsaveis), conteudo gerado (usuario mantem direitos, mas ClipIA pode exibir como showcase), uso aceitavel (nao gerar conteudo ilegal/odio), limitacao de responsabilidade, encerramento de conta
- Creditos comprados nao expiram mas nao sao reembolsaveis
- Videos gerados sao de propriedade do usuario
- ClipIA pode usar videos anonimizados para showcase/marketing (com opt-out)
- Idade minima: 18 anos
- Foro: comarca de Cascavel-PR

#### 2. Pagina /privacidade — Politica de Privacidade (LGPD)
Criar `frontend/src/app/privacidade/page.tsx` com:
- Politica completa conforme LGPD (Lei 13.709/2018)
- Controlador: Braga Consultoria, CNPJ 65.620.439/0001-62
- DPO/Encarregado: Guilherme Bezerra Braga, contato@clipia.com.br
- Dados coletados: nome, email, historico de uso, dados de pagamento (processados pelo MercadoPago)
- Bases legais: consentimento (cadastro), execucao contratual (servico), interesse legitimo (seguranca)
- Compartilhamento: Anthropic (roteiros), Microsoft (TTS), Pexels (media), MercadoPago (pagamentos)
- Retencao: dados mantidos enquanto conta ativa, 30 dias apos exclusao para dados de video, dados financeiros por 5 anos (obrigacao legal)
- Direitos do titular: acesso, correcao, exclusao, portabilidade (endpoint /auth/export-data)
- Cookies/Storage: apenas localStorage para sessao, sem tracking cookies
- Seguranca: HTTPS, senhas em bcrypt, JWT com expiracao

#### 3. Links no Footer
Adicionar links "Termos de Uso" e "Politica de Privacidade" no Footer.tsx existente.

#### 4. Checkbox no registro
Adicionar no formulario de registro (`frontend/src/app/auth/register/page.tsx`):
```
[ ] Li e aceito os [Termos de Uso](/termos) e a [Politica de Privacidade](/privacidade)
```
Desabilitar botao "Criar conta" ate marcar o checkbox.

### Estilo das paginas
- Usar o mesmo dark theme do app
- Layout: max-w-3xl mx-auto, titulo h1, subtitulos h2, texto em prose
- Usar classes Tailwind consistentes com o resto do app
- Data de vigencia: 04/04/2026

### Verificacao
```bash
cd frontend && npx tsc --noEmit
```

---

## TAREFA 5: Email Templates HTML Profissionais

### Contexto
O ClipIA envia emails via SMTP (Gmail). Atualmente os templates sao inline HTML basico em `app/auth/email.py`. Precisa de templates profissionais e bonitos.

### Template base atual (em app/auth/email.py)
```python
def _send_otp_email(subject, headline, intro, to_email, code, user_name):
    html = f"""
    <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto; padding: 32px;">
        <h2 style="color: #7c3aed;">ClipIA</h2>
        <p>Ola, {user_name}!</p>
        <p>{intro}</p>
        <div style="background: #f3f4f6; border-radius: 8px; padding: 20px; text-align: center; margin: 24px 0;">
            <span style="font-size: 32px; font-weight: bold; letter-spacing: 8px; color: #1f2937;">{code}</span>
        </div>
        <p style="color: #6b7280; font-size: 14px;">Este codigo expira em 10 minutos.</p>
    </div>
    """
```

### Branding
- Cor primaria: #7c3aed (roxo/purple-600)
- Cor secundaria: #a855f7 (purple-400)
- Fundo escuro: #0f0b1a
- Texto claro: #e2e8f0
- Font: sans-serif (Inter feel)
- Logo: texto "ClipIA" estilizado (nao tem imagem de logo, usar texto)

### Templates a criar

Criar arquivo `app/email_templates.py` com funcoes que retornam HTML string:

#### 1. `email_verification(user_name, code)` — Verificacao de email
- Assunto: "ClipIA — Verifique seu email"
- Header com logo ClipIA
- Saudacao personalizada
- Codigo OTP grande e destacado
- Texto "Expira em 10 minutos"
- Footer com "© 2026 ClipIA | clipia.com.br"

#### 2. `email_password_reset(user_name, code)` — Reset de senha
- Assunto: "ClipIA — Redefinir sua senha"
- Similar ao verification mas com texto de reset
- Aviso: "Se voce nao solicitou, ignore este email"

#### 3. `email_welcome(user_name)` — Boas-vindas (apos verificar email)
- Assunto: "Bem-vindo ao ClipIA! 🎬"
- Celebrar os 2 creditos gratis
- 3 passos rapidos: 1) Escolha um tema 2) A IA cria o video 3) Edite e publique
- CTA: botao "Criar meu primeiro video" → https://clipia.com.br/dashboard

#### 4. `email_purchase_confirmed(user_name, package_name, credits, price_display)` — Compra confirmada
- Assunto: "ClipIA — Compra confirmada: {credits} creditos"
- Resumo da compra: pacote, creditos, valor
- Saldo atualizado (nao precisa, so confirmar a compra)
- CTA: "Ir para o Dashboard"

#### 5. `email_video_ready(user_name, job_topic)` — Video pronto
- Assunto: "ClipIA — Seu video esta pronto! 🎬"
- Informar que o video sobre "{topic}" ficou pronto
- CTA: "Ver meu video" → https://clipia.com.br/dashboard

#### 6. `email_account_deleted(user_name)` — Conta excluida
- Assunto: "ClipIA — Sua conta foi excluida"
- Confirmar exclusao
- Informar que dados serao removidos em 30 dias
- Contato para duvidas

### Requisitos tecnicos
- HTML email compativel (inline styles, tabelas para layout se necessario)
- Testar em Gmail, Outlook, Apple Mail (usar tabelas para layout, nao flexbox/grid)
- Responsive: largura max 600px, funcionar em mobile
- Dark mode: usar media query `@media (prefers-color-scheme: dark)` com fallback
- Alt text em tudo
- Preheader text (texto invisivel que aparece na preview do email)
- Unsubscribe link placeholder no footer

### Integracao
Atualizar `app/auth/email.py` para usar os novos templates:
```python
from app.email_templates import email_verification, email_password_reset

def send_verification_email(to_email, code, user_name):
    html = email_verification(user_name, code)
    _send_email(to_email, f"ClipIA — Verifique seu email", html)
```

Criar funcao generica `_send_email(to, subject, html)` para reutilizar.

### Verificacao
```bash
source .venv/bin/activate
python -c "
from app.email_templates import email_verification
print(email_verification('Gui', '123456')[:200])
"
pytest tests/ -q
```

---

## TAREFA 6: Landing Page Copy — Foco em Conversao

### Contexto
A landing page do ClipIA esta em `frontend/src/app/page.tsx` e seus componentes. Precisa de copy otimizado para conversao de visitante → cadastro.

### Componentes da landing
```
HeroSection — Titulo principal, subtitulo, CTA
SocialProofBar — Numeros/metricas sociais
ShowcaseSection — Exemplos de videos gerados
DemoSection — Demo interativa de geracao
HowItWorks — Passos do processo
WaitlistForm — Formulario de cadastro/waitlist
Footer — Links e info
```

### Proposta de valor
ClipIA transforma qualquer tema em video curto pronto para publicar em menos de 2 minutos. O usuario nao precisa saber editar video — a IA faz tudo: roteiro, narracao em pt-BR, legendas sincronizadas, selecao de midia, e composicao final. Depois, pode editar tudo num editor visual antes de publicar.

### Publico-alvo
- Criadores de conteudo brasileiros (TikTok, Reels, Shorts)
- Social media managers de empresas
- Educadores que querem criar conteudo em video
- Qualquer pessoa que quer fazer videos mas nao sabe editar

### O que fazer

Leia todos os componentes da landing e reescreva o copy focando em:

#### 1. HeroSection
- Headline: impactante, max 8 palavras, foco no beneficio (nao na feature)
- Sub-headline: 1-2 frases explicando como funciona
- CTA primario: "Criar meu primeiro video gratis" (nao "Comecar", nao "Cadastrar")
- CTA secundario: "Ver demo" (scroll para DemoSection)
- Micro-copy abaixo do CTA: "2 videos gratis • Sem cartao de credito"

#### 2. SocialProofBar
- Numeros que impressionam (mesmo que projetados): "500+ videos criados", "2min tempo medio", "3 vozes pt-BR"
- Se nao tiver numeros reais, usar features: "Narracao natural em pt-BR", "Legendas automaticas", "4 templates de video"

#### 3. ShowcaseSection
- Titulo da secao: algo como "Veja o que a IA cria em 2 minutos"
- Cada exemplo de video precisa de titulo atrativo e tema

#### 4. HowItWorks
- 3 passos claros e simples:
  1. "Escolha um tema" — digite qualquer assunto
  2. "A IA cria tudo" — roteiro, narracao, legendas, video
  3. "Edite e publique" — ajuste no editor visual e exporte
- Cada passo com descricao de 1 linha

#### 5. DemoSection
- Titulo: "Experimente agora" ou "Veja a magia acontecer"
- Copy que convida a testar sem compromisso

#### 6. WaitlistForm → converter para RegisterCTA
- Se o usuario ja pode se cadastrar, mudar de waitlist para CTA de registro
- Titulo: "Comece a criar videos hoje"
- Subtitulo: "2 videos gratis, sem cartao de credito"
- Botao: link direto para /auth/register

#### 7. Footer
- Tagline curta: "Videos curtos com IA, feitos no Brasil 🇧🇷"
- Links organizados: Produto (Dashboard, Creditos), Legal (Termos, Privacidade), Contato

### Regras de copy
- pt-BR natural, sem anglicismos desnecessarios (usar "video" nao "content")
- Beneficio antes de feature ("Videos prontos em 2 min" > "Geracao automatizada com IA")
- Urgencia sutil ("Comece gratis hoje")
- Social proof onde possivel
- Cada headline deve funcionar sozinha (sem contexto)
- Nao usar superlativos vazios ("o melhor", "revolucionario")

### Verificacao
```bash
cd frontend && npx tsc --noEmit
```

---

## TAREFA 7: Preparacao para i18n

### Contexto
ClipIA e 100% pt-BR mas pode expandir para espanhol e ingles no futuro. Precisa extrair todas as strings hardcoded para um sistema de traducao.

### Stack
- Next.js 16 + React 19
- Nao usar libs de i18n complexas (next-intl, react-i18next) — apenas um objeto de strings simples por enquanto

### O que fazer

#### 1. Criar arquivo de strings `frontend/src/lib/strings.ts`
```typescript
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
```

#### 2. Varrer TODOS os .tsx e substituir strings hardcoded
Para cada arquivo em `frontend/src/`:
- Encontrar toda string pt-BR hardcoded
- Substituir por referencia ao `strings` object
- Import: `import { strings } from '@/lib/strings'`

Exemplo:
```tsx
// ANTES
<button>{loading ? "Entrando..." : "Entrar"}</button>

// DEPOIS
<button>{loading ? strings.auth.login.loading : strings.auth.login.submit}</button>
```

#### 3. NAO mexer em:
- CSS classes
- HTML attributes (aria-label pode usar strings, mas so se ja tiver texto)
- Nomes de variaveis/funcoes
- Console.log mensagens (podem ficar em ingles)
- Comentarios

### Verificacao
```bash
cd frontend && npx tsc --noEmit
# Verificar que nao sobrou string hardcoded pt-BR nos componentes:
grep -rn '"[A-Z][a-z].*"' frontend/src/components/ --include="*.tsx" | grep -v import | grep -v className | head -30
```

---

## TAREFA 8: Test Data Fixtures Realisticos

### Contexto
Os testes do ClipIA precisam de dados realisticos para simular cenarios de producao. Atualmente os testes usam dados minimos como `topic="test"`.

### O que criar

#### 1. `tests/fixtures/topics.py` — 50 topicos variados
```python
TOPICS = [
    # Educacional
    "5 curiosidades sobre o fundo do oceano que voce nao sabia",
    "Como funciona a memoria humana: 3 fatos cientificos",
    "A historia do cafe: da Etiopia ate sua xicara",
    # ... mais 47 topicos cobrindo:
    # - Educacional (ciencia, historia, tecnologia)
    # - Entretenimento (curiosidades, ranking, desafios)
    # - Business (dicas de produtividade, marketing)
    # - Lifestyle (receitas rapidas, dicas de saude)
    # - Trending (IA, cripto, sustentabilidade)
]

STYLES = ["educational", "storytelling", "news", "comedy"]
DURATIONS = [30, 45, 60, 90]
TEMPLATES = ["stock_narration", "gameplay_narration", "character_narration", "story_narration"]
```

#### 2. `tests/fixtures/scripts.py` — 5 scripts completos de exemplo
```python
SAMPLE_SCRIPTS = [
    {
        "title": "5 Curiosidades Sobre o Oceano",
        "narration": "Voce sabia que o oceano cobre mais de 70 por cento da superficie da Terra? ...",
        "scenes": [
            {
                "text": "O oceano e imenso...",
                "duration_hint": 8,
                "keywords_en": ["ocean", "deep sea", "underwater"],
            },
            # ... 3-5 cenas por script
        ],
    },
    # ... mais 4 scripts completos
]
```

#### 3. `tests/fixtures/words.py` — timestamps de exemplo
```python
SAMPLE_WORDS = [
    {"word": "Voce", "start": 0.0, "end": 0.3},
    {"word": "sabia", "start": 0.3, "end": 0.7},
    {"word": "que", "start": 0.7, "end": 0.9},
    {"word": "o", "start": 0.9, "end": 1.0},
    {"word": "oceano", "start": 1.0, "end": 1.5},
    # ... ~50 palavras com timestamps realisticos
]
```

#### 4. `tests/fixtures/webhooks.py` — payloads MercadoPago
```python
def make_mp_webhook_payload(payment_id: str, status: str = "approved", external_ref: str = "") -> dict:
    """Generate realistic MercadoPago webhook payload."""
    return {
        "action": "payment.updated",
        "api_version": "v1",
        "data": {"id": payment_id},
        "date_created": "2026-04-04T20:00:00.000-03:00",
        "id": 12345678,
        "live_mode": True,
        "type": "payment",
        "user_id": "142847978",
    }

def make_mp_payment_response(payment_id: str, status: str, external_ref: str, amount: float) -> dict:
    """Generate realistic MercadoPago payment API response."""
    return {
        "id": int(payment_id),
        "status": status,
        "status_detail": "accredited" if status == "approved" else "pending_contingency",
        "external_reference": external_ref,
        "transaction_amount": amount,
        "currency_id": "BRL",
        "payment_method_id": "pix",
        "payment_type_id": "bank_transfer",
        "payer": {
            "email": "test_user@testuser.com",
            "identification": {"type": "CPF", "number": "12345678909"},
        },
        "date_created": "2026-04-04T20:00:00.000-03:00",
        "date_approved": "2026-04-04T20:00:05.000-03:00" if status == "approved" else None,
    }

# Edge cases
WEBHOOK_INVALID_JSON = b"not json at all"
WEBHOOK_MISSING_DATA = {"action": "payment.updated"}
WEBHOOK_WRONG_ACTION = {"action": "merchant_order.updated", "data": {"id": "123"}}
WEBHOOK_NO_PAYMENT_ID = {"action": "payment.updated", "data": {}}
```

#### 5. `tests/fixtures/users.py` — perfis de usuario para testes
```python
TEST_USERS = {
    "new": {"email": "novo@teste.com", "name": "Usuario Novo", "password": "senha123", "credits": 0, "verified": False},
    "verified": {"email": "verificado@teste.com", "name": "Usuario Verificado", "password": "senha123", "credits": 2, "verified": True},
    "rich": {"email": "rico@teste.com", "name": "Usuario Rico", "password": "senha123", "credits": 100, "verified": True},
    "broke": {"email": "semcredito@teste.com", "name": "Sem Credito", "password": "senha123", "credits": 0, "verified": True},
    "admin": {"email": "admin@clipia.com", "name": "Admin", "password": "admin123", "credits": 999, "verified": True, "plan": "admin"},
}

# Emails de teste que cobrem edge cases
EDGE_CASE_EMAILS = [
    "normal@gmail.com",
    "COM.MAIUSCULAS@EMAIL.COM",        # deve normalizar
    "  espacos@email.com  ",            # deve fazer trim
    "acentuação@domínio.com.br",        # caracteres especiais
    "nome+tag@gmail.com",               # gmail alias
    "a@b.co",                           # minimo valido
]

INVALID_EMAILS = [
    "",
    "@semlocal.com",
    "semdominio@",
    "sem arroba",
    "espacos no meio@email.com",
    "a" * 300 + "@long.com",           # muito longo
]
```

#### 6. `tests/fixtures/__init__.py` — re-export tudo
```python
from .topics import TOPICS, STYLES, DURATIONS, TEMPLATES
from .scripts import SAMPLE_SCRIPTS
from .words import SAMPLE_WORDS
from .webhooks import make_mp_webhook_payload, make_mp_payment_response
from .users import TEST_USERS, EDGE_CASE_EMAILS, INVALID_EMAILS
```

### Integracao com testes existentes
Atualizar `tests/conftest.py` para importar fixtures:
```python
from tests.fixtures import TEST_USERS, SAMPLE_SCRIPTS
```

Atualizar testes existentes para usar dados realisticos em vez de strings genericas como "test topic".

### Verificacao
```bash
source .venv/bin/activate
pytest tests/ -q
python -c "from tests.fixtures import TOPICS; print(f'{len(TOPICS)} topics loaded')"
```
