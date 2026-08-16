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
| `core/whatsapp_signup.py` | Conexão do número pelo Embedded Signup. |
| `core/whatsapp_views.py` | Webhook, API da caixa de entrada e a página. |
| `frontend/templates/whatsapp_inbox.html` | A caixa de entrada, em `/whatsapp/`. |
| `core/tests_whatsapp.py` | 48 testes. Rodar antes de qualquer mexida. |

### A caixa de entrada

Segue a mesma direção visual da tela de Alunos, minimalista com disciplina
suíça, porque a professora salta entre as duas dezenas de vezes por dia.

O elemento que organiza a tela é o **trilho da janela**: uma barra no topo da
conversa que esvazia conforme as 24 horas correm. Quando ela acaba, o campo de
escrita se transforma sozinho no seletor de modelos aprovados. A regra mais
confusa do WhatsApp Business deixa de ser algo para decorar e passa a ser algo
que se vê.

Duas decisões que vale não desfazer sem pensar:

- **Mensagem enviada pelo celular não ganha cor nova**, ganha borda tracejada e
  o rótulo "pelo celular". Cor escassa é regra da casa, e a coexistência já
  produz muita mensagem de saída que o sistema não originou.
- **Etiqueta só marca o que exige decisão.** "Janela aberta" seria a maioria
  das linhas, então não vira etiqueta. O que aparece é "só com modelo", quando
  há mensagem por responder e a janela já fechou.

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

### O que acontece no clique de "Conectar WhatsApp"

Implementado em `core/whatsapp_signup.py`. Em ordem:

1. O popup devolve um `code` (pelo callback do `FB.login`) e o `waba_id` (por
   `postMessage`, evento `FINISH_WHATSAPP_BUSINESS_APP_ONBOARDING`). São dois
   caminhos diferentes, e o código só é usado quando os dois chegaram.
2. Trocamos o código por um token de longa duração. O código é de uso único e
   expira em minutos, então tudo acontece na mesma requisição.
3. Assinamos a nossa app à WABA do cliente. Sem isto o webhook nunca dispara e
   a caixa de entrada fica muda **sem dar erro nenhum**.
4. Descobrimos o `phone_number_id`: no fluxo de coexistência o popup manda só
   o `waba_id`.
5. Disparamos as duas importações, contatos e histórico.

> **Não registramos o número.** Na coexistência ele já está registrado pelo
> aplicativo do celular, e chamar `POST /{phone_number_id}/register` aqui
> quebraria a conexão. Tem teste a garantir que essa chamada não acontece,
> porque nenhum teste de caminho feliz pegaria isso.

Falha na importação do histórico **não derruba a conexão**: as conversas novas
continuam chegando, só o passado não veio junto, e o aviso fica em
`WhatsAppAccount.last_error`.

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

## Cobrança pelo canal (Fase 3)

`send_billing_message` decide sozinho como falar:

- **Janela aberta e texto escrito:** manda o texto da professora, que é de
  graça e soa como ela.
- **Janela fechada:** usa o modelo aprovado do tipo pedido, preenchendo nome,
  valor e vencimento nas chaves `{{1}}`, `{{2}}`, `{{3}}`.

O `BillingLog` e o `WhatsAppMessage` nascem na **mesma transação** e ficam
ligados, o que permite a ficha do aluno mostrar entrega e leitura. Falha no
envio não deixa `BillingLog` órfão: registrar cobrança que não saiu seria pior
do que não registrar.

O endpoint `/api/whatsapp/billing/status/` diz à interface **como** a mensagem
vai sair, e o botão "Enviar pelo EducaFlow" só aparece quando o envio vai
funcionar. Botão que promete e falha é pior do que botão ausente.

A interface vive em `frontend/templates/cobranca.html` mais
`core/static/script.js`.

> [!warning] `cobranca_standalone.html` é código morto
> Nenhuma view a referencia. A cobrança real é a `cobranca.html`, incluída
> pelo `index.html`. Perdi tempo editando a errada.

## Anexos

Baixados assim que a mensagem chega, porque **a URL da Meta expira** e depois o
`media_id` não serve para nada. Teto de 16 MB. Falha no download nunca derruba
o webhook: anexo perdido é ruim, webhook em erro é pior, porque a Meta
reentrega o lote e acaba desativando a assinatura.

## O que ainda não existe

- **Recebimento nunca foi exercitado**: precisa de URL pública, e a Meta não
  alcança `localhost`. É a metade não testada do sistema.
- Envio de mídia e de áudio **pela** caixa de entrada.
- Preenchimento das variáveis do modelo na tela da caixa de entrada: o envio de
  template por ali ainda vai sem parâmetros. A cobrança preenche sozinha.
- Atualização em tempo real: hoje a tela pergunta ao servidor a cada 12
  segundos. Chega para uma escola, não chega para dezenas de professores no
  mesmo número.

## `sent` não é `entregue`

Aprendido do jeito caro em 16/08/2026.

Quando a Cloud API responde com um `wamid`, ela só **aceitou** a mensagem. A
entrega vem depois, por webhook, como `delivered` ou `failed`. O nosso
`WhatsAppMessage.status` nasce `sent`, e é isso que ele significa: aceito.

> [!danger] Sem webhook, uma falha de entrega é invisível
> Três mensagens foram dadas como entregues durante os testes porque a API
> aceitou todas. Nenhuma chegou. O motivo só apareceu no painel da Meta, em
> "Verifique webhooks de teste":
>
> ```
> "status": "failed",
> "errors": [{ "code": 130497,
>   "title": "Business account is restricted from messaging users in this country." }]
> ```

**Erro 130497:** conta não verificada, com número de teste americano, não pode
mandar mensagem para números brasileiros. O número de teste da Meta serve para
validar código, não para ver mensagem chegando no Brasil.

Isto é o argumento mais forte a favor de configurar o webhook cedo: o
tratamento de `failed` já existe e mostra o erro na conversa, mas nunca rodou.

## Armadilha do ambiente local

`staticfiles/script.js` pode ficar **velho** e ser servido no lugar de
`core/static/script.js`, fazendo parecer que a alteração de JS não pegou.
Encontrado em 14/08/2026 com uma cópia de março. Se mexeu no JS e nada mudou:

```bash
.venv/Scripts/python.exe dev_local.py collectstatic --noinput
```

E depois recarregue ignorando o cache do browser.
