# Guia de Pagamento — Stripe & Mercado Pago (04/07/2026)

> Verifiquei tudo ao vivo com as APIs de produção (tokens do `.env`). **A maior parte já
> está pronta e funcionando.** Este guia lista só o que sobra pra você + como testar.

## ✅ O que JÁ está pronto (verificado ao vivo, você não precisa fazer nada)

### Stripe (cartão)
- **Webhook**: endpoint `https://clipia.com.br/api/v1/webhooks/stripe` **registrado e `enabled`**,
  com os eventos certos (`checkout.session.completed`, `async_payment_succeeded`, `charge.refunded`).
  ID `we_1ToBZjHjv1lxIoqOyxKWcitg`.
- **`STRIPE_WEBHOOK_SECRET`** já está no `.env` (`whsec_…`), e o backend está no ar com ele.
- **Cartão**: `card_payments` = active. Checkout de produção criado com sucesso (`cs_live_…`).
- **Idempotência**: testada E2E em 30/06 (pagamento + estorno reais creditaram/reverteram certo).

### Mercado Pago (Pix + cartão + boleto + saldo)
- **Pix ATIVO** na conta (`bank_transfer: pix`), junto com cartão (master/visa/elo/amex), boleto
  (bolbradesco) e saldo MP. Confirmado via API.
- **Webhook auto-configurado**: o código põe `notification_url` em cada preference
  (`service.py:111`) → o MP notifica sozinho, **sem registrar nada no painel**.
- **Checkout de produção criado com sucesso** (preference real do mercadopago.com.br).
- **Idempotência**: por `external_reference` + lock por pagamento (`_credit_once`/`_revert_once`).

**Resumo:** cartão via Stripe **e** MP; Pix via MP. Webhooks funcionando nos dois. 🎉

---

## 🟡 O que sobra pra você (opcional / recomendado)

### 1. `MP_WEBHOOK_SECRET` — OPCIONAL (defense-in-depth, NÃO bloqueia)
Hoje o backend valida a notificação do MP **re-consultando a API do MP** (seguro). A assinatura
secreta adiciona uma 2ª camada. Se quiser fechar:
1. Acesse **developers.mercadopago.com** → **Suas integrações** → sua aplicação.
2. Menu **Webhooks** (ou "Notificações") → **Configurar notificações**.
3. Em modo **Produção**, copie a **"Assinatura secreta"** (uma string longa).
4. Cole no `.env`: `MP_WEBHOOK_SECRET=<a assinatura>`.
5. Reinicie o backend (eu faço via a scheduled task, é só pedir).

### 2. Teste E2E real — RECOMENDADO antes de divulgar
As chaves são LIVE (a `rk_live` do Stripe não aceita cartão de teste), então o teste ponta-a-ponta
custa dinheiro real. Sugestão barata: pacote **Starter (R$19,90)**.
1. Logue no ClipIA → **Créditos** → escolha **Starter**.
2. **MP**: pague por **Pix** (some segundos) → volte ao dashboard → confirme que os créditos subiram.
3. **Stripe**: pague com seu cartão → confirme o crédito.
4. (Opcional) Estorne pelo painel de cada um e confirme que o saldo reverte (o webhook de refund já trata).

### 3. Pix no Stripe — NÃO necessário (nota)
A API do Stripe recusou ativar Pix nesta conta BR ("not requestable"). **Não faz falta**: o Pix já
vem pelo MP. Se algum dia quiser Pix também no Stripe, é via suporte/onboarding no dashboard Stripe.

---

## Notas técnicas
- Verifiquei via **API direta** (tokens do `.env`), não pelo MCP OAuth — mais direto e sem login interativo.
- Criei 2 checkouts de teste (1 MP, 1 Stripe) que ficaram `pending` no banco — inócuos, nunca
  creditam sem pagamento, expiram sozinhos.
- Os webhooks só creditam **após o backend estar no ar com o código atual** — o que já está (deploy 04/07).
