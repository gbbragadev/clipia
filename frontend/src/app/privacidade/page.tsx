import { strings } from '@/lib/strings'

export default function PrivacidadePage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-16 prose prose-invert prose-purple">
      <h1 className="text-3xl font-bold mb-8">Política de Privacidade</h1>
      <p className="text-slate-400 mb-8">Data de vigência: 04/04/2026</p>

      <h2>1. Introdução</h2>
      <p>
        Esta Política de Privacidade descreve como a Braga Consultoria (CNPJ 65.620.439/0001-62), controladora do site ClipIA (clipia.com.br), coleta, usa e protege seus dados pessoais em conformidade com a Lei Geral de Proteção de Dados Pessoais (LGPD - Lei 13.709/2018).
      </p>

      <h2>2. Dados Coletados</h2>
      <p>Nós coletamos os seguintes dados quando você utiliza o ClipIA:</p>
      <ul>
        <li><strong>Dados de cadastro:</strong> Nome, e-mail e senha (armazenada em formato de hash criptografado irreversível).</li>
        <li><strong>Histórico de uso:</strong> Tópicos de vídeos gerados, preferência de voz e histórico de jobs.</li>
        <li><strong>Dados financeiros:</strong> Histórico de pacotes adquiridos. O processamento do pagamento é feito pelo MercadoPago; o ClipIA não armazena e não tem acesso aos dados completos do seu cartão de crédito.</li>
        <li><strong>Dados técnicos:</strong> Endereço IP (usado apenas para segurança e limitação de taxa/rate limit).</li>
      </ul>

      <h2>3. Bases Legais para Tratamento</h2>
      <p>O tratamento de seus dados é realizado com base nas seguintes justificativas da LGPD:</p>
      <ul>
        <li><strong>Consentimento:</strong> Fornecido no momento do cadastro na plataforma.</li>
        <li><strong>Execução de Contrato:</strong> Para a prestação do serviço de geração de vídeos.</li>
        <li><strong>Interesse Legítimo:</strong> Para segurança, prevenção a fraudes e melhoria dos serviços.</li>
      </ul>

      <h2>4. Compartilhamento de Dados</h2>
      <p>Para fornecer o serviço, integramos com os seguintes provedores terceirizados:</p>
      <ul>
        <li><strong>Anthropic (Claude API):</strong> Recebe os tópicos solicitados para criação dos roteiros.</li>
        <li><strong>Microsoft Edge TTS:</strong> Processa o texto para a síntese da narração em áudio.</li>
        <li><strong>Pexels API:</strong> Utilizada para buscar mídias relacionadas aos vídeos.</li>
        <li><strong>MercadoPago:</strong> Processa as transações financeiras.</li>
      </ul>

      <h2>5. Armazenamento e Retenção</h2>
      <p>
        Seus dados são mantidos enquanto sua conta estiver ativa. Em caso de exclusão da conta:
      </p>
      <ul>
        <li>Dados de vídeo gerados e mídias associadas são removidos em até 30 dias.</li>
        <li>Dados de faturamento e recibos podem ser retidos por até 5 anos para cumprimento de obrigação legal ou regulatória.</li>
      </ul>

      <h2>6. Cookies e Tecnologias Semelhantes</h2>
      <p>
        O ClipIA não utiliza cookies de rastreamento (tracking cookies). Utilizamos apenas o <code>localStorage</code> do seu navegador para manter a sessão (tokens JWT) ativa e garantir a segurança do acesso.
      </p>

      <h2>7. Direitos do Titular</h2>
      <p>Você tem o direito de solicitar a qualquer momento, mediante requisição na plataforma ou por e-mail:</p>
      <ul>
        <li>Acesso aos seus dados.</li>
        <li>Correção de dados incompletos ou inexatos.</li>
        <li>Portabilidade dos dados a outro fornecedor de serviço ou produto (disponível através das configurações da sua conta).</li>
        <li>Eliminação dos dados pessoais tratados com o consentimento do titular.</li>
      </ul>

      <h2>8. Segurança</h2>
      <p>
        Empregamos medidas técnicas e organizacionais como uso de HTTPS (SSL/TLS) em todas as comunicações, criptografia de senhas (bcrypt) e expiração restrita de tokens de acesso (JWT) para proteger as informações contra acessos não autorizados.
      </p>

      <h2>9. Contato do Encarregado (DPO)</h2>
      <p>
        Se você tiver dúvidas sobre nossa Política de Privacidade, entre em contato com nosso DPO/Encarregado:<br />
        Guilherme Bezerra Braga<br />
        E-mail: <strong>contato@clipia.com.br</strong>
      </p>
    </div>
  )
}
