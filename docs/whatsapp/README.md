# WhatsApp Business no EducaflowOne

Canal oficial do WhatsApp dentro do sistema: as conversas com pais e alunos
entram na ficha do aluno, e cobrança e lembrete de aula passam a sair daqui em
vez de serem copiados à mão.

Piloto com a Cini English (Bianca). A arquitetura já é multi-conta: nada aqui
assume uma professora só.

---

## O modelo de coexistência

O número roda **ao mesmo tempo** no aplicativo do WhatsApp Business, no celular
da professora, e na Cloud API. A Meta chama isto de *coexistence*, disponível
desde maio de 2025 e global desde novembro de 2025.

Isto é o que torna o piloto viável: a professora não perde o aplicativo, não
perde o histórico e não muda a rotina dela. O sistema entra por cima.

Três consequências que atravessam o código inteiro:

1. **Nem toda mensagem enviada saiu do sistema.** O que ela manda pelo celular
   chega como *echo* (webhook `smb_message_echoes`) e é gravado com
   `origin=app`. Ignorar isso deixaria a caixa de entrada mostrando metade da
   conversa, e ela responderia duas vezes a mesma pergunta.

2. **A janela de 24 horas só vale para a API.** Mensagem enviada pelo aplicativo
   não tem essa restrição. Por isso a janela é contada a partir da última
   mensagem **recebida**, e só é consultada na hora de enviar pela API.

3. **Se ela ficar mais de 14 dias sem abrir o aplicativo, a conexão cai.** Vale
   monitorar depois de férias escolares.

O que a coexistência desliga no aplicativo dela: **listas de transmissão**,
grupos sincronizados, chamadas de voz e vídeo, status, catálogo e pedidos,
mensagens temporárias e visualização única. A substituição de transmissão passa
a ser template pela API, que funciona melhor mas custa por mensagem.

---

## Como as peças se dividem

| Ficheiro | Responsabilidade |
|----------|------------------|
| `core/whatsapp.py` | Fala com a Meta. Telefones, assinatura, cliente HTTP, leitura do payload. Não conhece modelos. |
| `core/whatsapp_service.py` | Regra de negócio que toca o banco. Processa webhook, envia, resolve contato e conversa. |
| `core/whatsapp_views.py` | Webhook e estado da conta. |
| `core/tests_whatsapp.py` | 38 testes. Rodar antes de qualquer mexida. |

### Modelos

- **`WhatsAppAccount`** número conectado, um por professor dono. O token fica
  cifrado (`set_access_token` / `get_access_token`), nunca ler o campo direto.
- **`WhatsAppContact`** um número que conversa com a escola. Nasce na primeira
  mensagem, mesmo sem aluno ligado. Guarda o consentimento.
- **`WhatsAppConversation`** a thread. Guarda quem atende e quando a janela
  fecha.
- **`WhatsAppMessage`** cada mensagem, com `direction` e `origin`.
- **`WhatsAppTemplate`** modelo aprovado, ligado ao uso interno pelo `purpose`.
- **`WhatsAppWebhookEvent`** idempotência. A Meta reentrega quando não recebe
  200 rápido; sem esta tabela, uma lentidão do banco vira mensagem duplicada.

### Quem vê o quê

Uma escola tem vários professores num número só. A conversa herda o responsável
de `Student.assigned_teacher`; o dono da conta vê tudo, o parceiro vê só os
alunos dele. A regra está em `WhatsAppConversation.visible_to`.

---

## O nono dígito

A maior fonte de contato duplicado no Brasil. O `wa_id` que a Meta devolve às
vezes vem **sem** o nono dígito (números antigos), e o cadastro feito pela
professora quase sempre vem **com**. As duas formas são a mesma pessoa.

Nenhuma busca por telefone compara strings direto: tudo passa por
`whatsapp.phone_variants`, que gera as duas formas. Telefone fixo não ganha
nono dígito inventado, senão o sistema mandaria mensagem para um número que não
existe.

---

## Passos na Meta (não dá para fazer por código)

São **dois negócios distintos**, e misturar os dois é o erro mais caro aqui.

**1. EducaFlow, o seu CNPJ, vira Tech Provider.**
Business Manager verificado, app criada no App Dashboard com o produto
WhatsApp, e Embedded Signup implementado. É isto que libera a coexistência:
não existe caminho manual pelo painel.

**2. A escola da Bianca vira negócio cliente.**
Business Manager e WABA próprios, conectando pelo Embedded Signup. Assim o
número, as conversas e a responsabilidade de LGPD ficam com ela. Concentrar
tudo no CNPJ da EducaFlow tornaria você o responsável legal pelas conversas dos
pais de alunos de cada professor que entrar depois.

Requisitos do lado dela: aplicativo do WhatsApp Business 2.24.17 ou superior, e
o número em uso há pelo menos 7 dias.

**Depois de conectar:** a sincronização do histórico tem janela de 24 horas, e
mídia só dos últimos 14 dias. Alguém precisa acompanhar no dia da virada.

---

## Variáveis de ambiente

Ver `.env.example`, secção WhatsApp. Lembrete que já custou caro neste projeto:
**variável alterada no Railway só entra em vigor no próximo arranque do
container.** Trocar todas e fazer um Redeploy único no fim.

A URL a cadastrar na Meta é `https://www.educaflowone.com.br/api/webhooks/whatsapp/`,
uma só para todas as contas: quem identifica a conta é o `phone_number_id`
dentro do payload.

---

## Consentimento, e por que não fazer disparo em massa

Mensagem iniciada pela escola (template) só sai para quem tem
`opt_in_status = granted`. Não é preciosismo: um disparo em massa do tipo
"agora falem só por aqui" vira denúncia de uma fatia dos destinatários, a
qualidade do número cai para RED e o limite de envio despenca justamente no
primeiro mês do piloto.

A migração dos pais deve ser feita em ondas, com consentimento registrado
antes, e a origem do consentimento guardada em `opt_in_source` (contrato,
matrícula, resposta no WhatsApp).

O sistema também reconhece pedidos de saída: uma mensagem que seja só "sair",
"parar", "cancelar" e afins revoga o consentimento sozinha.

---

## Rodar os testes

```bash
.venv/Scripts/python.exe dev_local.py test core.tests_whatsapp
```

Nunca `manage.py` direto: o `.env` local tem credenciais reais, e o runner as
neutraliza antes de o Django carregar as settings.

---

## O que ainda não existe

- Interface da caixa de entrada (Fase 2).
- Embedded Signup, o fluxo de conectar o número (hoje a conta é criada à mão).
- Ligação com cobrança e lembrete de aula (Fase 3): o serviço já tem
  `conversation_for_student` e `template_for`, falta chamar a partir das views
  do financeiro e do calendário.
- Download e guarda das mídias recebidas: o `media_id` é gravado, mas o
  ficheiro ainda não é baixado, e a URL da Meta expira.
