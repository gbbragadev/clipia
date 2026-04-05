import { strings } from '@/lib/strings'

export default function TermosPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-16 prose prose-invert prose-purple">
      <h1 className="text-3xl font-bold mb-8">Termos de Uso</h1>
      <p className="text-slate-400 mb-8">Data de vigência: 04/04/2026</p>

      <h2>1. Aceitação dos Termos</h2>
      <p>
        Ao acessar e usar o ClipIA (clipia.com.br), você concorda em cumprir estes Termos de Uso. O ClipIA é operado pela Braga Consultoria (CNPJ 65.620.439/0001-62), com sede na comarca de Cafelândia-PR. Se você não concorda com qualquer parte destes termos, não deve usar nossos serviços.
      </p>

      <h2>2. Descrição do Serviço</h2>
      <p>
        O ClipIA é uma plataforma de Software as a Service (SaaS) baseada em Inteligência Artificial para geração automatizada de vídeos curtos. Os usuários podem inserir tópicos e gerar vídeos contendo roteiro, narração, legendas e mídia de fundo.
      </p>

      <h2>3. Cadastro e Elegibilidade</h2>
      <p>
        Para usar o serviço, você deve ter pelo menos 18 anos de idade. Você é responsável por manter a confidencialidade das credenciais de sua conta.
      </p>

      <h2>4. Créditos e Pagamentos</h2>
      <p>
        O uso dos serviços de geração de vídeo consome créditos. Os créditos podem ser adquiridos em pacotes através de nosso processador de pagamentos (MercadoPago).
        Os créditos adquiridos não expiram, mas <strong>não são reembolsáveis</strong> após a compra.
      </p>

      <h2>5. Conteúdo Gerado e Direitos Autorais</h2>
      <p>
        Os vídeos gerados através da plataforma são de propriedade do usuário. No entanto, o usuário concorda em conceder ao ClipIA uma licença irrevogável para usar vídeos gerados de forma anonimizada para fins de showcase, marketing e exibição na plataforma (exceto se o usuário expressamente solicitar opt-out).
      </p>

      <h2>6. Uso Aceitável</h2>
      <p>
        Você concorda em não utilizar o ClipIA para gerar ou promover conteúdo:
      </p>
      <ul>
        <li>Ilegal, fraudulento ou enganoso;</li>
        <li>Que promova discurso de ódio, violência ou discriminação;</li>
        <li>Que viole direitos autorais, marcas registradas ou propriedade intelectual de terceiros;</li>
        <li>Pornográfico ou sexualmente explícito.</li>
      </ul>

      <h2>7. Limitação de Responsabilidade</h2>
      <p>
        A IA comete erros. O ClipIA não garante a exatidão, precisão ou adequação dos fatos gerados nos roteiros, narrações ou mídia. O usuário é inteiramente responsável por revisar o conteúdo antes de sua publicação em outras redes. A Braga Consultoria não será responsável por danos diretos ou indiretos decorrentes do uso da plataforma.
      </p>

      <h2>8. Encerramento de Conta</h2>
      <p>
        Reservamo-nos o direito de suspender ou encerrar sua conta a qualquer momento, por qualquer motivo, sem aviso prévio, especialmente em casos de violação destes Termos.
      </p>

      <h2>9. Foro</h2>
      <p>
        Estes Termos são regidos pelas leis brasileiras. Fica eleito o foro da comarca de Cascavel-PR para dirimir quaisquer controvérsias.
      </p>
    </div>
  )
}
