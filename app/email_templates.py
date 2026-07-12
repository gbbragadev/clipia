def _base_template(subject: str, preheader: str, content: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject}</title>
    <style>
        body {{ margin: 0; padding: 0; font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0f0b1a; color: #e2e8f0; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 32px 20px; }}
        .header {{ text-align: center; margin-bottom: 32px; }}
        .logo {{ color: #7c3aed; font-size: 28px; font-weight: bold; letter-spacing: -0.5px; margin: 0; }}
        .card {{ background-color: #1e1b29; border: 1px solid #332e44; border-radius: 12px; padding: 32px; }}
        h1 {{ margin-top: 0; color: #ffffff; font-size: 20px; font-weight: 600; }}
        p {{ line-height: 1.6; margin: 16px 0; color: #cbd5e1; }}
        .code-box {{ background-color: #2d283e; border: 1px solid #4a445e; border-radius: 8px; padding: 24px; text-align: center; margin: 32px 0; }}
        .code {{ font-size: 36px; font-weight: bold; letter-spacing: 12px; color: #ffffff; margin: 0; }}
        .btn {{ display: inline-block; background-color: #7c3aed; color: #ffffff; text-decoration: none; font-weight: 600; padding: 14px 28px; border-radius: 8px; text-align: center; margin: 24px 0; }}
        .footer {{ text-align: center; margin-top: 32px; padding-top: 32px; border-top: 1px solid #332e44; color: #64748b; font-size: 13px; }}
        .preheader {{ display: none; max-height: 0px; overflow: hidden; }}
    </style>
</head>
<body>
    <div class="preheader">{preheader}</div>
    <div class="container">
        <div class="header">
            <h2 class="logo">ClipIA</h2>
        </div>
        <div class="card">
            {content}
        </div>
        <div class="footer">
            <p>© 2026 ClipIA | clipia.com.br</p>
            <p>Se você não deseja mais receber nossos e-mails, <a href="#" style="color: #7c3aed;">cancele sua inscrição</a>.</p>
        </div>
    </div>
</body>
</html>"""


def email_verification(user_name: str, code: str) -> str:
    content = f"""
    <h1>Verifique seu e-mail</h1>
    <p>Olá, {user_name}!</p>
    <p>Obrigado por se cadastrar no ClipIA. Para ativar sua conta e ganhar seus 2 créditos grátis, use o código abaixo:</p>
    <div class="code-box">
        <p class="code">{code}</p>
    </div>
    <p style="font-size: 14px; color: #94a3b8;">Este código expira em 10 minutos.</p>
    """
    return _base_template("ClipIA — Verifique seu email", "Seu código de verificação do ClipIA chegou.", content)


def email_password_reset(user_name: str, code: str) -> str:
    content = f"""
    <h1>Redefinir sua senha</h1>
    <p>Olá, {user_name}!</p>
    <p>Recebemos uma solicitação para redefinir a senha da sua conta ClipIA. Use o código abaixo para criar uma nova senha:</p>
    <div class="code-box">
        <p class="code">{code}</p>
    </div>
    <p style="font-size: 14px; color: #94a3b8;">Este código expira em 10 minutos. Se você não solicitou a redefinição, por favor, ignore este e-mail.</p>
    """
    return _base_template(
        "ClipIA — Redefinir sua senha", "Código para redefinição de senha da sua conta ClipIA.", content
    )


def email_welcome(user_name: str) -> str:
    content = f"""
    <h1>Bem-vindo ao ClipIA! 🎬</h1>
    <p>Olá, {user_name}!</p>
    <p>Sua conta foi verificada com sucesso e nós acabamos de adicionar <strong>2 créditos grátis</strong> a ela.</p>
    <p>Em 3 passos rápidos, você pode criar seu primeiro vídeo:</p>
    <ol style="color: #cbd5e1; line-height: 1.6; margin: 16px 0 32px 0;">
        <li>Escolha um tema ou assunto</li>
        <li>A IA escreve o roteiro, gera a narração e seleciona a mídia</li>
        <li>Você revisa, edita se precisar e exporta!</li>
    </ol>
    <div style="text-align: center;">
        <a href="https://clipia.com.br/dashboard" class="btn">Criar meu primeiro vídeo</a>
    </div>
    """
    return _base_template("Bem-vindo ao ClipIA! 🎬", "Você ganhou 2 créditos para criar seu primeiro vídeo.", content)


def email_purchase_confirmed(user_name: str, package_name: str, credits: int, price_display: str) -> str:
    content = f"""
    <h1>Compra Confirmada!</h1>
    <p>Olá, {user_name}!</p>
    <p>Seu pagamento foi aprovado e seus créditos já estão disponíveis na sua conta. Muito obrigado por escolher o ClipIA!</p>
    <div style="background-color: #2d283e; border: 1px solid #4a445e; border-radius: 8px; padding: 20px; margin: 24px 0;">
        <p style="margin: 0 0 8px 0;"><strong>Pacote:</strong> {package_name}</p>
        <p style="margin: 0 0 8px 0;"><strong>Créditos adicionados:</strong> {credits}</p>
        <p style="margin: 0;"><strong>Valor:</strong> {price_display}</p>
    </div>
    <div style="text-align: center;">
        <a href="https://clipia.com.br/dashboard" class="btn">Ir para o Dashboard</a>
    </div>
    """
    return _base_template(
        f"ClipIA — Compra confirmada: {credits} créditos", f"Seu pagamento de {price_display} foi aprovado.", content
    )


def email_video_ready(user_name: str, job_topic: str, job_id: str) -> str:
    content = f"""
    <h1>Seu vídeo está pronto! 🎬</h1>
    <p>Olá, {user_name}!</p>
    <p>A IA terminou de criar o seu vídeo sobre <strong>"{job_topic}"</strong>. Ele já está disponível para você revisar, editar ou baixar — o que você vê no editor é o que exporta.</p>
    <div style="text-align: center;">
        <a href="https://clipia.com.br/editor/{job_id}" class="btn">Ver meu vídeo</a>
    </div>
    """
    return _base_template(
        "ClipIA — Seu vídeo está pronto! 🎬", f"O vídeo sobre '{job_topic}' acabou de ficar pronto.", content
    )


def email_account_deleted(user_name: str) -> str:
    content = f"""
    <h1>Sua conta foi excluída</h1>
    <p>Olá, {user_name},</p>
    <p>Confirmamos que sua conta no ClipIA foi excluída com sucesso, conforme sua solicitação.</p>
    <p>Lembramos que, de acordo com nossa Política de Privacidade, seus dados pessoais e de vídeo serão removidos de forma definitiva ou anonimizados em até 30 dias.</p>
    <p>Lamentamos ver você partir. Se mudar de ideia, estaremos sempre de portas abertas.</p>
    """
    return _base_template("ClipIA — Sua conta foi excluída", "Sua conta no ClipIA foi excluída com sucesso.", content)
