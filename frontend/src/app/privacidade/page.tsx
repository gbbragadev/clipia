import type { Metadata } from 'next'

import { canonicalUrl } from '@/lib/site'

export const metadata: Metadata = {
  title: 'Política de Privacidade — ClipIA',
  description: 'Política de privacidade e tratamento de dados pessoais da plataforma ClipIA.',
  alternates: { canonical: canonicalUrl('/privacidade') },
  openGraph: {
    title: 'Política de Privacidade — ClipIA',
    description: 'Como o ClipIA trata e protege dados pessoais.',
    url: canonicalUrl('/privacidade'),
    type: 'website',
  },
}

export default function PrivacidadePage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-16 prose prose-invert prose-a:text-coral">
      <h1 className="text-3xl font-bold mb-8">Política de Privacidade</h1>
      <p className="text-slate-400 mb-8">Data de vigência: 02/07/2026</p>

      <h2>1. Introdução</h2>
      <p>
        Esta Política de Privacidade descreve como a Braga Consultoria (CNPJ 65.620.439/0001-62), controladora do site ClipIA (clipia.com.br), coleta, usa e protege seus dados pessoais em conformidade com a Lei Geral de Proteção de Dados Pessoais (LGPD - Lei 13.709/2018).
      </p>

      <h2>2. Dados Coletados</h2>
      <p>Nós coletamos os seguintes dados quando você utiliza o ClipIA:</p>
      <ul>
        <li><strong>Dados de cadastro:</strong> Nome, e-mail e senha (armazenada em formato de hash criptografado irreversível).</li>
        <li><strong>Histórico de uso:</strong> Tópicos de vídeos gerados, preferência de voz e histórico de jobs.</li>
        <li><strong>Dados financeiros:</strong> Histórico de pacotes adquiridos, valores e status das transações. O processamento do pagamento é feito pelos provedores <strong>Stripe</strong> (primário) e <strong>Mercado Pago</strong> (secundário); o ClipIA não armazena e não tem acesso aos dados completos do seu cartão de crédito.</li>
        <li><strong>Dados técnicos:</strong> Endereço IP (usado apenas para segurança e limitação de taxa/rate limit).</li>
      </ul>

      <h2>3. Bases Legais para Tratamento</h2>
      <p>O tratamento de seus dados é realizado com base nas seguintes justificativas da LGPD:</p>
      <ul>
        <li><strong>Consentimento:</strong> Fornecido de forma <strong>expressa e inequívoca</strong> no momento do cadastro, por meio da marcação de um <em>checkbox</em> específico de aceitação desta Política de Privacidade ao criar a conta.</li>
        <li><strong>Execução de Contrato:</strong> Para a prestação do serviço de geração de vídeos.</li>
        <li><strong>Interesse Legítimo:</strong> Para segurança, prevenção a fraudes e melhoria dos serviços.</li>
      </ul>

      <h2>4. Compartilhamento de Dados</h2>
      <p>
        Para fornecer o serviço, compartilhamos dados estritamente necessários com os seguintes subprocessadores (provedores terceirizados que tratam dados pessoais em nosso nome). Cada um recebe apenas os dados indispensáveis à sua função:
      </p>
      <ul>
        <li><strong>OpenAI:</strong> recebe o tópico solicitado e o prompt para geração do roteiro (LLM), a narração sintetizada para transcrição (Whisper, fallback de legendas) e os prompts visuais para geração de imagens (gpt-image).</li>
        <li><strong>xAI (Grok):</strong> recebe o tópico e o prompt como provedor de geração de roteiro alternativo (fallback).</li>
        <li><strong>OpenRouter:</strong> intermediário que roteia a geração de roteiro (DeepSeek) e a geração de clipes de vídeo por IA (ByteDance Seedance); recebe o tópico/prompt e, no caso de vídeo, os parâmetros da cena.</li>
        <li><strong>Groq:</strong> recebe o áudio da narração para transcrição com timestamp (geração de legendas).</li>
        <li><strong>Microsoft (serviço Edge TTS):</strong> recebe o texto da narração para síntese de voz padrão.</li>
        <li><strong>ElevenLabs:</strong> recebe o texto da narração para vozes premium, clonagem e design de voz, e efeitos sonoros (SFX); no caso de clonagem, recebe as amostras de áudio enviadas pelo usuário.</li>
        <li><strong>Pexels:</strong> recebe palavras-chave de busca (em inglês) para retornar vídeos e imagens de estoque usados como mídia de fundo.</li>
        <li><strong>Stripe:</strong> processa pagamentos (cartão e Pix) e eventos de estorno; recebe dados de transação necessários à liquidação.</li>
        <li><strong>Mercado Pago:</strong> processa pagamentos como provedor secundário; recebe dados de transação necessários à liquidação.</li>
        <li><strong>Provedor de e-mail transacional (SMTP):</strong> recebe o seu endereço de e-mail para entrega de códigos de verificação, redefinição de senha e confirmações de conta.</li>
      </ul>
      <p>
        Alguns desses provedores (em especial os de IA) estão sediados fora do Brasil, caracterizando transferência internacional de dados, realizada apenas para a execução do serviço e com provedores que possuem práticas de privacidade compatíveis com a LGPD. Atualizaremos esta lista sempre que um novo subprocessador for adicionado.
      </p>

      <h2>5. Armazenamento e Retenção</h2>
      <p>
        Seus dados são mantidos enquanto sua conta estiver ativa. Ao solicitar a exclusão da conta, aplicamos um processo de <strong>anonimização imediata (soft-delete)</strong> seguido de retenção seletiva:
      </p>
      <ul>
        <li><strong>Anonimização imediata:</strong> assim que a exclusão é confirmada, seus dados identificáveis são tornados irrevinculáveis — o e-mail é substituído por um endereço anônimo, os créditos são zerados, o plano é marcado como excluído, a senha é substituída por um hash aleatório e os códigos de verificação são descartados. A partir desse ponto, sua conta deixa de estar acessível e seus dados não podem mais ser associados a você pela plataforma.</li>
        <li><strong>Retenção por obrigação legal:</strong> registros de transações financeiras (compras, recibos, status de pagamento) e logs de auditoria necessários à segurança, prevenção de fraudes e cumprimento de obrigações contábeis, fiscais e regulatórias podem ser mantidos pelo prazo exigido pela legislação aplicável (inclusive por até 5 anos).</li>
        <li><strong>Deleção física periódica:</strong> os arquivos de mídia (vídeos, áudios e imagens gerados) e demais dados retidos são eliminados fisicamente de forma periódica por processos de limpeza do armazenamento, após o decurso dos prazos de retenção aplicáveis.</li>
      </ul>
      <p>
        Você pode solicitar a exportação dos seus dados a qualquer momento antes da exclusão (ver Seção 7).
      </p>

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
