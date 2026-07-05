import logging
from pathlib import Path

from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    # API Keys
    PEXELS_API_KEY: str = ""

    # Biblioteca de midia de fundo via Google Drive (rclone). RCLONE_EXE = caminho absoluto se o
    # binario (winget) nao estiver no PATH do worker. Remote gdrive ja configurado (OAuth da conta).
    RCLONE_EXE: str = "rclone"
    RCLONE_REMOTE: str = "gdrive"

    # LLM (OpenRouter — API compativel com OpenAI; usado p/ roteiro e IA do editor)
    OPEN_ROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    LLM_MODEL: str = "deepseek/deepseek-v4-pro"  # slug OpenRouter; alt: deepseek/deepseek-v4-flash
    # Fallback FREE no OpenRouter quando o modelo principal falha (cota estourada / erro). "" desliga.
    LLM_FALLBACK_MODEL: str = "nvidia/nemotron-3-nano-30b-a3b:free"

    # Cascata de provedores LLM (failover por budget): OpenRouter pago -> OpenAI -> xAI -> OpenRouter free.
    # complete_text tenta cada um EM ORDEM ate receber resposta nao-vazia; key vazia = provedor pulado.
    # (OpenRouter pago retorna 402 quando sem credito -> a cascata segue automaticamente p/ o proximo.)
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    LLM_OPENAI_KEY: str = ""  # se vazio, usa OPENAI_API_KEY
    LLM_OPENAI_MODEL: str = "gpt-4o-mini"
    LLM_XAI_BASE_URL: str = "https://api.x.ai/v1"
    LLM_XAI_KEY: str = ""
    LLM_XAI_MODEL: str = "grok-2-latest"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://clipia:clipia_dev@localhost:5435/clipia"

    # Auth
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Redis
    REDIS_URL: str = "redis://localhost:6382/0"

    # Paths
    STORAGE_DIR: Path = BASE_DIR / "storage"
    REFERENCE_VOICE: Path = BASE_DIR / "reference_voices" / "narrator_ptbr.wav"
    FONT_PATH: Path = BASE_DIR / "fonts" / "Montserrat-Bold.ttf"

    # Video
    VIDEO_WIDTH: int = 1080
    VIDEO_HEIGHT: int = 1920
    VIDEO_FPS: int = 30
    WATERMARK_ENABLED: bool = True
    WATERMARK_TEXT: str = "clipia.com.br"

    # Outro sting de marca (selo de ~1.5s no final de cada video)
    OUTRO_ENABLED: bool = True
    OUTRO_DURATION: float = 1.5  # piso em segundos; cresce se o whisper for maior
    OUTRO_BLUR_SIGMA: float = 16.0
    OUTRO_DARKEN: float = 0.30  # delta de brightness aplicado ao frame congelado
    OUTRO_LOGO_WIDTH: int = 520  # largura do logo no selo (px)
    OUTRO_AUDIO_PATH: Path = BASE_DIR / "app" / "assets" / "outro" / "whisper.wav"
    OUTRO_LOGO_PATH: Path = BASE_DIR / "app" / "assets" / "outro" / "logo.png"

    # Render engine para o export editado (hibrido: FFmpeg na geracao inicial, Remotion no export)
    RENDER_ENGINE: str = "remotion"  # "remotion" | "ffmpeg"
    REMOTION_RENDER_TIMEOUT: int = 300

    # Selecao de midia: "heuristic" (default, sem dep) | "clip" (rerank semantico, exige sentence-transformers)
    MEDIA_RERANK: str = "heuristic"
    # Quality gate pos-render (ffprobe/ffmpeg): grava quality_warning no job se o video sair ruim
    QUALITY_GATE_ENABLED: bool = True
    # SFX (whoosh) nas transicoes de cena via ElevenLabs. No-op gracioso sem ELEVENLABS_API_KEY.
    SFX_ENABLED: bool = True
    # Musica de fundo automatica na geracao inicial (mood por template; faixas royalty-free locais)
    AUTO_MUSIC_ENABLED: bool = True
    AUTO_MUSIC_VOLUME: float = 0.12

    # Dialogo multi-locutor (text_to_dialogue): 2 vozes ElevenLabs pt-BR. Troque por env se quiser.
    DIALOGUE_VOICE_A: str = "KHmfNHtEjHhLK9eER20w"  # Fernanda (pt-BR, feminina)
    DIALOGUE_VOICE_B: str = "aRsdx5i9kl9PWUbkzxIp"  # Bruno - ClipIA (pt-BR, masculina, Voice Design)

    # GPU
    DEVICE: str = "cuda"
    WHISPER_MODEL_SIZE: str = "large-v3"
    WHISPER_COMPUTE_TYPE: str = "float16"

    # Voice Providers
    ELEVENLABS_API_KEY: str = ""

    # ASR Providers (Phase A: remote only — no local Whisper)
    GROQ_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    ASR_FALLBACK_ENABLED: bool = False
    GROQ_WHISPER_MODEL: str = "whisper-large-v3"
    OPENAI_WHISPER_MODEL: str = "whisper-1"

    # GPT Image 2
    GPT_IMAGE_MODEL: str = "gpt-image-2"
    GPT_IMAGE_QUALITY: str = "medium"  # "low" | "medium" | "high"
    GPT_IMAGE_MODERATION: str = "low"  # "auto" | "low"

    # Kling AI (legado — substituido por video IA via OpenRouter)
    KLING_ACCESS_KEY: str = ""
    KLING_SECRET_KEY: str = ""

    # Video IA via OpenRouter (geracao assincrona; ver app/services/video_gen_provider.py)
    # Slugs: bytedance/seedance-2.0-fast (default) | bytedance/seedance-2.0 | bytedance/seedance-1-5-pro
    OPENROUTER_VIDEO_MODEL: str = "bytedance/seedance-2.0-fast"
    VIDEO_GEN_RESOLUTION: str = "720p"  # 480p (barato) | 720p. 2.0-fast nao tem 1080p.
    VIDEO_GEN_ASPECT_RATIO: str = "9:16"
    VIDEO_GEN_CLIP_SECONDS: int = 5  # duracao de cada clipe por cena (Seedance aceita 4-15)
    VIDEO_GEN_POLL_INTERVAL: int = 15  # segundos entre polls do job assincrono
    VIDEO_GEN_TIMEOUT: int = 600  # teto por clipe (10 min)
    # Custo em creditos do template de video IA. Preco e por TOKEN = w*h*dur*24/1024.
    # Ex.: 2.0-fast 720p 9:16 ~= R$0,67/s; um Short ~30s ~= R$20 de API -> ~30 creditos com margem.
    # Ajuste junto com OPENROUTER_VIDEO_MODEL/VIDEO_GEN_RESOLUTION.

    # Credit costs
    CREDIT_COST_EDGE: int = 1
    CREDIT_COST_ELEVENLABS: int = 2
    CREDIT_COST_CUSTOM_AUDIO: int = 1
    CREDIT_COST_AI_IMAGE: int = 5
    CREDIT_COST_AI_VIDEO: int = 30  # template premium de video IA (ver nota de precificacao acima)
    CREDIT_COST_VOICE_DESIGN: int = 5  # criar voz custom (ElevenLabs Voice Design) — operacao paga
    CREDIT_COST_VOICE_CLONE: int = 5  # clonar voz (ElevenLabs Instant Voice Clone) — operacao paga

    # Bonus de creditos ao verificar email. Default 2 (publico). Elevar temporariamente
    # para um beta fechado (ex: 20) para que testadores consigam gerar varios videos sem
    # comprar; voltar para 2 antes do lancamento publico. Nao afeta o bonus do referrer
    # (sempre +2 fixo, ver app/auth/routes.py).
    WELCOME_CREDIT_BONUS: int = 2

    # Promocao de compra (beta): % de creditos BONUS sobre o pacote comprado, aplicado no
    # credito pos-webhook (_credit_once — ponto unico MP+Stripe). 0 desliga. Ex.: 20 -> pacote
    # popular (30) credita 36. Nao mexe em preco cobrado; rollback = voltar a 0 no .env + restart.
    PURCHASE_BONUS_PERCENT: int = 0

    # Guardrail anti-burn: teto DIARIO de geracoes de video IA (Seedance ~R$0,67/s, ~R$20/Short) por
    # usuario. 0 desliga. Mesmo conta admin/seed (999k creditos) nao queima $ ilimitado num dia — foi
    # o vetor do gasto de ~$6 (tester com conta admin). Vale pra TODOS os planos, inclusive admin.
    MAX_AI_VIDEO_PER_DAY: int = 3

    # Guardrail anti-burn: teto de cenas por video. Cada cena de ai_video/ai_image dispara UMA
    # geracao PAGA (Seedance ~R$3,35/cena; gpt-image ~R$0,x/cena), enquanto o credito cobrado e
    # FIXO por template. Um roteiro com cenas demais (LLM excede as "4-6" do prompt, ou prompt
    # injection pedindo exaustividade) multiplica o custo sem multiplicar a receita. O clamp e
    # PROPORCIONAL a duracao (max(6, ceil(dur/4))) p/ nao cortar videos longos legitimos, com este
    # teto duro absoluto. Ver app/services/scriptwriter.py (aplicado apos o parse do roteiro).
    MAX_SCENES_PER_VIDEO: int = 40

    # MercadoPago
    MP_ACCESS_TOKEN: str = ""
    MP_WEBHOOK_SECRET: str = ""
    # Stripe (segundo provedor de pagamento — Checkout hospedado, Cartao + Pix).
    # Hosted Checkout so precisa da SECRET key no backend; a publishable key (client-side) nao e usada.
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    FRONTEND_URL: str = "http://localhost:3003"
    BACKEND_URL: str = ""  # https://api.clipia.com.br in production

    # Anti-bot (Cloudflare Turnstile no cadastro). Vazio = desabilitado (cadastro funciona sem captcha).
    # Gere as keys no painel Cloudflare (Turnstile): secret aqui, site key em NEXT_PUBLIC_TURNSTILE_SITE_KEY (frontend).
    TURNSTILE_SECRET_KEY: str = ""

    # Bypass do Turnstile para o gate automatizado de go-live (validate_readiness.py) e
    # testes E2E internos. Quando configurado, requests com o header
    # `X-Readiness-Bypass: <READINESS_BYPASS_SECRET>` pulam a verificacao anti-bot.
    # Vazio = bypass desabilitado (producao segura). NUNCA commitar o valor real.
    READINESS_BYPASS_SECRET: str = ""

    # Rate Limiting
    RATE_LIMIT_AUTH: str = "5/minute"
    RATE_LIMIT_GENERATE: str = "10/minute"
    RATE_LIMIT_DEFAULT: str = "60/minute"

    # CORS
    CORS_ORIGINS: str = "http://localhost:3003"  # comma-separated, "*" for dev

    # SMTP (email verification)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@clipia.com.br"

    # Suporte ao usuario (beta). Email vira Reply-To do welcome email; recebimento exige
    # Cloudflare Email Routing (Resend e send-only). WhatsApp em formato wa.me (so digitos,
    # ex: 5545999999999); vazio = link omitido do email.
    SUPPORT_EMAIL: str = "suporte@clipia.com.br"
    SUPPORT_WHATSAPP: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

_logger = logging.getLogger(__name__)

_WEAK_SECRETS = {"dev-secret-change-in-production", "changeme", "secret", ""}


def validate_production_settings(s: Settings) -> None:
    """Validate critical settings. Call on startup."""
    if s.JWT_SECRET in _WEAK_SECRETS or len(s.JWT_SECRET) < 32:
        raise ValueError("JWT_SECRET inseguro! Gere um com: openssl rand -hex 32")
    warn_keys = ("OPEN_ROUTER_API_KEY", "PEXELS_API_KEY", "GROQ_API_KEY", "OPENAI_API_KEY", "ELEVENLABS_API_KEY")
    for key in warn_keys:
        if not getattr(s, key):
            _logger.warning("Config: %s nao configurado — funcionalidade limitada", key)
    if not s.SMTP_HOST:
        _logger.warning(
            "Config: SMTP_HOST nao configurado — emails de verificacao e reset de senha NAO serao enviados "
            "(o codigo OTP so vai para o log). Configure SMTP_* no .env."
        )
    if not s.MP_ACCESS_TOKEN:
        _logger.warning(
            "Config: MP_ACCESS_TOKEN nao configurado — compra de creditos (Mercado Pago) DESABILITADA; "
            "o checkout vai falhar. Preencha com o Access Token de producao do Mercado Pago para habilitar."
        )
    elif not s.MP_WEBHOOK_SECRET:
        _logger.warning(
            "Config: MP_WEBHOOK_SECRET nao configurado — a validacao de assinatura do webhook sera pulada. "
            "A confirmacao ainda e segura (consulta a API do MP), mas configure o secret para defesa extra."
        )
    if not s.STRIPE_SECRET_KEY:
        _logger.warning(
            "Config: STRIPE_SECRET_KEY nao configurado — pagamento via Stripe DESABILITADO (so Mercado Pago)."
        )
    elif not s.STRIPE_WEBHOOK_SECRET:
        _logger.warning(
            "Config: STRIPE_WEBHOOK_SECRET nao configurado — webhook do Stripe valida via consulta a API "
            "(retrieve da session) em vez de assinatura. Configure o whsec_ para defesa extra."
        )
