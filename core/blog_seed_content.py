# -*- coding: utf-8 -*-
"""
Conteúdo de lançamento do blog.

Oito artigos escritos para o mesmo leitor: o professor particular brasileiro
que dá aula sozinho, atende pelo WhatsApp e faz a própria cobrança. Cada um
ataca uma busca que essa pessoa realmente faz no Google ("quanto cobrar por
aula particular", "como conseguir alunos", "aluno não pagou o que fazer"), e
termina levando ao cadastro.

Isto é semente, não conteúdo fixo: o comando `blog_seed` cria os artigos como
rascunho se ainda não existirem e nunca sobrescreve o que já foi editado no
/admin/. Depois de criados, a fonte da verdade é o banco.

Para adicionar mais um: copie um dicionário, mude o slug, e rode o comando de
novo. Só o que tem slug novo entra.
"""

# ── Editorias ───────────────────────────────────────────────────────────────
CATEGORIAS = [
    {
        "name": "Volta às aulas",
        "slug": "volta-as-aulas",
        "order": 1,
        "description": "Como começar o semestre com a agenda cheia, o preço ajustado e "
                       "nenhum aluno perdido no caminho.",
    },
    {
        "name": "Dicas de inglês",
        "slug": "dicas-de-ingles",
        "order": 2,
        "description": "Atividades, explicações e materiais prontos para usar na próxima aula.",
    },
    {
        "name": "Gestão da aula",
        "slug": "gestao-da-aula",
        "order": 3,
        "description": "Agenda, planejamento, materiais e rotina de quem dá aula sozinho.",
    },
    {
        "name": "Dinheiro e cobrança",
        "slug": "dinheiro-e-cobranca",
        "order": 4,
        "description": "Preço, recebimento, inadimplência e imposto para professor particular.",
    },
    {
        "name": "Conseguir alunos",
        "slug": "conseguir-alunos",
        "order": 5,
        "description": "Divulgação, indicação e conversão de interessado em aluno pagante.",
    },
]


# ── Artigos ─────────────────────────────────────────────────────────────────
ARTIGOS = [

{
    "slug": "quanto-cobrar-por-aula-particular",
    "categoria": "dinheiro-e-cobranca",
    "title": "Quanto cobrar por aula particular em 2026: o cálculo que quase ninguém faz",
    "seo_title": "Quanto cobrar por aula particular em 2026 | Guia de preço",
    "dek": "A conta certa não começa perguntando quanto os outros cobram. Começa "
           "perguntando quantas horas por mês você consegue, de verdade, dar aula.",
    "seo_description": "Como calcular o preço da sua hora-aula particular: horas "
                       "vendáveis, custo real, tempo invisível e quando reajustar.",
    "keywords": "quanto cobrar aula particular, preço hora aula, valor aula particular 2026",
    "cta_title": "Saiba, sem planilha, quanto você faturou este mês",
    "cta_text": "O EDUCAflowOne soma aula por aula, mostra quem está devendo e emite "
                "recibo. Você descobre o seu preço real olhando um número, não a memória.",
    "cta_button": "Ver meu financeiro grátis",
    "content": """
Toda vez que a pergunta aparece num grupo de professores, a resposta vem no mesmo formato: alguém diz o próprio preço, outra pessoa diz que é caro, uma terceira diz que é barato, e ninguém sai dali sabendo o que fazer. O problema é que preço de aula particular não é uma tabela. É uma conta, e ela tem quatro números.

## O primeiro número: quantas horas você consegue vender

Não é quantas horas você tem. É quantas horas alguém quer.

Aula particular acontece na janela em que o aluno está livre: entre 7h e 8h da manhã, entre 12h e 13h, e das 18h às 21h. Somando fim de semana, um professor em tempo integral vende entre 20 e 28 horas por semana. Quem dá aula como segunda renda vende entre 6 e 12.

Escreva o seu número. Ele é o teto do seu faturamento, e quase todo mundo o superestima.

## O segundo número: o tempo que você trabalha sem receber

Uma aula de 60 minutos custa muito mais que 60 minutos:

- procurar e preparar material: 15 a 30 minutos
- corrigir tarefa e responder mensagem: 10 a 20 minutos por aluno, por semana
- remarcar, confirmar, lembrar: 5 minutos que sempre viram 20
- cobrar, conferir Pix, mandar recibo: uma tarde inteira por mês

Uma pesquisa informal em qualquer grupo de professor mostra a mesma proporção: para cada hora dada, existe entre meia hora e uma hora de trabalho não faturado. Se você ignora esse tempo, você não está cobrando por aula. Está cobrando por aula e trabalhando de graça no resto.

## O terceiro número: o seu custo por hora

Some tudo que sai da sua conta por causa da aula, por mês:

| Item | Valor típico por mês |
| --- | --- |
| Internet e telefone | R$ 120 |
| Plataforma de aula, materiais, cópias | R$ 60 a R$ 150 |
| Deslocamento, se atende presencial | R$ 150 a R$ 500 |
| Formação continuada, livros, cursos | R$ 100 |
| Imposto, se MEI | cerca de R$ 76 |

Divida o total pelas horas vendáveis do mês. Esse é o piso absoluto: abaixo dele, cada aula dada tira dinheiro do seu bolso.

## O quarto número: o quanto você quer ganhar

Aqui entra a parte que professor tem dificuldade de dizer em voz alta. Escolha um valor mensal líquido. Some o custo. Divida pelas horas vendáveis realistas do mês. Some de 20 a 30 por cento pelo tempo invisível da segunda seção.

Um exemplo fechado, para o número sair do abstrato:

- meta líquida: R$ 5.000
- custo mensal: R$ 700
- horas vendáveis realistas: 80 por mês (20 por semana)
- (5.000 + 700) dividido por 80 = R$ 71 por hora
- somando 25 por cento de tempo invisível: **R$ 89 por hora**

Arredonde para R$ 90. Esse é o seu preço, e ele não tem nada a ver com o que o professor do grupo do WhatsApp cobra.

## Onde a faixa de mercado entra

Ela entra depois, como termômetro, não como régua. Em 2026, aula particular de inglês online no Brasil circula entre R$ 60 e R$ 140 a hora, com reforço escolar de fundamental mais perto de R$ 50 a R$ 80 e preparação para exame de proficiência ou aula para executivo passando de R$ 150.

Se a sua conta deu muito acima da faixa, o problema não é o preço: é o número de horas vendáveis, que provavelmente está baixo demais. Se deu muito abaixo, você está subsidiando o aluno.

> Preço baixo não traz mais aluno. Traz aluno que some quando aparece alguém dez reais mais barato. Quem compra por preço nunca é fiel ao preço, é fiel ao próximo preço.

## Quatro formas de cobrar mais sem aumentar a hora

1. **Venda pacote, não aula avulsa.** Oito aulas pagas na frente resolvem a sua previsibilidade e a assiduidade do aluno de uma vez.
2. **Cobre a hora cheia mesmo em aula de 50 minutos.** É o padrão de consultório, de estúdio e de terapia, e ninguém estranha.
3. **Tenha uma política de cancelamento escrita.** Cancelou com menos de 24 horas, a aula conta. Sem isso, o seu preço é uma sugestão.
4. **Cobre pelo que está em volta.** Correção de redação, relatório para os pais, material personalizado: ou está no preço, ou é um serviço à parte.

[[cta]]

## Quando e como reajustar

Uma vez por ano, sempre no mesmo mês. Janeiro e agosto funcionam bem, porque coincidem com a virada de semestre e o aluno já espera mudança.

Avise com 30 dias de antecedência, por escrito, com uma frase só: "A partir de março o valor da hora passa a ser R$ 95. Continuo com o mesmo horário reservado para você." Não peça desculpa e não explique inflação. Quem vai embora por 10 por cento já estava indo embora por outro motivo.

## O erro que custa mais caro que o preço errado

É não saber quanto se ganhou. Professor que anota aula em caderno e pagamento na memória descobre o próprio faturamento com três meses de atraso, e quase sempre para menos.

Antes de discutir preço, tenha o número. Quantas aulas você deu no mês passado, quanto entrou, quem ainda não pagou. Com esses três dados na tela, a conversa sobre preço deixa de ser opinião.
""",
},

{
    "slug": "volta-as-aulas-checklist-professor-particular",
    "categoria": "volta-as-aulas",
    "title": "Volta às aulas: o checklist do professor particular para não começar o semestre no vermelho",
    "seo_title": "Volta às aulas: checklist do professor particular | 2026",
    "dek": "As três semanas antes do semestre decidem o seu ano inteiro. É quando "
           "o aluno escolhe se continua, e quando o horário bom ainda está livre.",
    "seo_description": "Checklist de volta às aulas para professor particular: "
                       "confirmar alunos, reajustar preço, remontar a grade e captar "
                       "antes de todo mundo.",
    "keywords": "volta às aulas professor particular, retomar alunos, agenda semestre",
    "cta_title": "Comece o semestre com a agenda montada",
    "cta_text": "Grade de horários, confirmação de aula, cobrança e planejamento no "
                "mesmo lugar. Monte o semestre em uma tarde e passe o resto do ano dando aula.",
    "cta_button": "Montar minha agenda grátis",
    "content": """
Existe uma janela curta, mais ou menos três semanas antes da volta às aulas, em que a família senta para decidir o que o filho vai fazer no semestre e o adulto decide se retoma o inglês. Quem fala com essas pessoas dentro da janela enche a agenda. Quem espera o semestre começar disputa o que sobrou.

Este é o roteiro para atravessar essa janela sem perder nada.

## Três semanas antes: fale com quem já é seu aluno

Retomar aluno antigo custa uma mensagem. Conseguir aluno novo custa semanas. Ainda assim, a maioria dos professores começa pelo lado caro.

Faça a lista de todo mundo que teve aula com você nos últimos doze meses, incluindo quem parou. Mande mensagem individual, nunca em lista de transmissão:

> "Oi, Ana. Estou montando os horários do semestre e separei terça e quinta às 18h, que era o seu horário. Quer que eu segure para você? Preciso confirmar até sexta."

Três coisas fazem essa mensagem funcionar: ela é pessoal, oferece um horário concreto, e tem prazo. Mensagem sem prazo vira "depois eu te falo" e nunca mais.

## Duas semanas antes: decida o preço e comunique

Volta às aulas é o único momento do ano em que reajuste não gera atrito, porque o aluno já espera que tudo mude de preço. Se você não reajustou no ano passado, esse é o momento.

Comunique junto com a confirmação de horário, no mesmo texto, sem parágrafo separado e sem pedido de desculpa. Preço em mensagem própria vira negociação. Preço dentro da confirmação de horário vira informação.

## Duas semanas antes: monte a grade no papel, não na cabeça

Desenhe a semana e marque três coisas:

- **horário nobre**: 7h, 12h e das 18h às 21h. É o que todo mundo quer e o que você deve preencher primeiro
- **horário morto**: as faixas que ninguém pede. Ou você aceita que ficam vazias, ou cria algo para elas (aula em dupla mais barata, turma de conversação, atendimento a quem trabalha em escala)
- **intervalo real**: aula colada em aula por quatro horas parece ótimo na planilha e destrói você em três semanas

Deixe pelo menos duas janelas livres para reposição. Sem elas, todo cancelamento vira dor de cabeça no mês inteiro.

[[cta]]

## Uma semana antes: escreva as suas regras

Não precisa de contrato de advogado. Precisa de uma página, mandada por escrito para todo aluno novo e para todo aluno que volta:

1. valor da hora e forma de pagamento
2. dia do vencimento
3. política de cancelamento: com quantas horas de antecedência a aula não é cobrada
4. o que acontece com falta sem aviso
5. período de férias e feriados

Quase toda briga de professor particular com aluno nasce de um item dessa lista que nunca foi dito em voz alta. Mandar por escrito no começo evita a conversa constrangedora em maio.

## Uma semana antes: capte com o que você já tem

Antes de pensar em anúncio pago, use os canais gratuitos:

- **peça indicação a quem está satisfeito**, com pedido específico: "Você conhece alguém que esteja procurando aula de inglês para este semestre?" funciona muito melhor que "indica aí"
- **avise a escola do bairro** que você tem horário para reforço
- **publique uma vez** no seu perfil dizendo quantas vagas restam e em quais horários. Vaga com número tem urgência, "aceito alunos" não tem
- **reative quem sumiu**: quem teve aula com você em 2025 e parou é o público mais fácil que existe

## Primeira semana: as duas coisas que seguram o aluno

O aluno decide se fica nas duas primeiras aulas, e ele decide por dois motivos que não têm a ver com didática:

**Ele precisa sentir que existe um plano.** Na primeira aula, mostre onde ele está e aonde vai chegar em três meses. Não precisa ser um documento bonito. Precisa existir.

**Ele precisa ver progresso rápido.** Deixe uma vitória pequena e concreta acontecer logo: uma conversa de dois minutos que ele conseguiu sustentar, uma prova antiga que ele agora resolve. Progresso invisível vira desistência em abril.

## O que fazer no domingo antes do primeiro dia

Confirme por mensagem, uma a uma, as aulas da semana. Parece exagero e não é: a taxa de falta na primeira semana cai pela metade quando existe confirmação, porque a rotina de todo mundo ainda está desmontada.

Depois disso, o semestre já está de pé. O resto é dar aula, que é a parte que você sabe fazer.
""",
},

{
    "slug": "aluno-nao-pagou-como-cobrar",
    "categoria": "dinheiro-e-cobranca",
    "title": "O aluno não pagou: como cobrar sem perder o aluno nem a noite de sono",
    "seo_title": "Aluno não pagou a aula: como cobrar sem constrangimento",
    "dek": "Cobrar aluno é a parte que ninguém ensinou na faculdade. Existe um jeito "
           "que funciona, e ele começa antes do vencimento.",
    "seo_description": "Como cobrar aluno particular que atrasou: mensagens prontas, "
                       "prazos, quando parar de dar aula e como evitar o problema.",
    "keywords": "cobrar aluno particular, inadimplência aula particular, mensagem de cobrança",
    "cta_title": "Nunca mais lembre de cobrança de cabeça",
    "cta_text": "O EDUCAflowOne avisa o vencimento, manda a mensagem no WhatsApp com o "
                "Pix junto e dá baixa sozinho quando o dinheiro cai. Você só confere.",
    "cta_button": "Automatizar minha cobrança",
    "content": """
Existe um tipo específico de mal-estar que só professor particular conhece: dar uma aula ótima para alguém que está devendo três, e terminar a aula sem conseguir tocar no assunto.

O problema quase nunca é o aluno mal-intencionado. É que a cobrança depende de você lembrar, escolher as palavras e ter coragem, três vezes por mês, para pessoas de quem você gosta. Qualquer sistema que dependa disso falha.

## Por que a conversa é difícil

Porque a relação é próxima e o valor é pequeno. Ninguém abre processo por R$ 320. Então o professor engole, e o aluno, que muitas vezes só esqueceu, entende que a data não importa muito.

O que resolve isso não é firmeza no dia da cobrança. É previsibilidade antes dela.

## As três decisões que evitam 90 por cento dos atrasos

**1. Cobre antes, não depois.** Pacote pago na frente, ou mensalidade com vencimento no dia 5, sempre. Aula avulsa paga no fim do mês é o desenho que mais gera inadimplência, porque acumula valor e some da memória.

**2. Tenha um dia fixo.** Vencimento no mesmo dia para todo mundo transforma cobrança em rotina, e rotina não precisa de coragem.

**3. Diga a regra no começo.** Uma frase, no primeiro dia: "O pagamento é até o dia 5. Depois de 15 dias em aberto, eu preciso pausar as aulas até regularizar." Dita no começo, é combinado. Dita depois do atraso, é ameaça.

## A escada de cobrança, em quatro degraus

Suba um degrau por vez, e nunca pule para o último.

### Degrau 1: o lembrete, três dias antes

> "Oi, Marcos! Passando para lembrar que a mensalidade de março vence quinta, dia 5. O Pix é a chave educaflow@email.com. Qualquer coisa me avisa."

Esse lembrete sozinho resolve a maioria dos casos, porque a maioria dos casos é esquecimento puro.

### Degrau 2: o aviso no dia seguinte ao vencimento

> "Oi, Marcos! O pagamento de março venceu ontem e ainda não caiu aqui. Deve ter passado batido. Segue o Pix de novo: [chave]. Me avisa quando puder."

Tom leve, sem cobrança moral. "Deve ter passado batido" dá ao outro uma saída digna, e é quase sempre verdade.

[[cta]]

### Degrau 3: a conversa, com sete a dez dias de atraso

Aqui muda o tom, e o assunto sai do valor e vai para a combinação:

> "Marcos, o pagamento de março ainda está em aberto. Prefiro resolver isso agora, antes de acumular com abril. Consegue fechar até sexta, ou faz mais sentido dividirmos em duas partes?"

Oferecer o parcelamento é a parte contraintuitiva que funciona. Quem está sem dinheiro trava e some. Quem recebe uma alternativa responde.

### Degrau 4: a pausa, com quinze dias

> "Marcos, como a gente combinou no começo, vou pausar as aulas até regularizar março. Seu horário de terça fica reservado por duas semanas. Assim que resolver, é só me avisar que retomamos."

Isso não é punição, e não deve soar como punição. É a regra que você anunciou no primeiro dia, sendo cumprida. Reservar o horário por um prazo mantém a porta aberta.

## O que não fazer, nunca

- **Dar aula de graça em silêncio esperando ele lembrar.** Você fica com raiva, ele nem percebe, e a relação apodrece pelo lado de dentro.
- **Cobrar no meio da aula ou na frente da criança.** Cobrança é assunto de adulto, por mensagem, fora do horário da aula.
- **Mandar indireta em story.** Todo mundo entende, e o único que fica mal na foto é você.
- **Abrir exceção sem prazo.** "Me paga quando puder" tem uma tradução única, e é "nunca".

## O caso do aluno que some devendo

Acontece. Depois de duas tentativas sem resposta em duas semanas, mande uma mensagem final, curta, sem drama, deixando o valor e a chave Pix registrados. Depois, encerre.

Para valores até vinte salários mínimos existe o Juizado Especial Cível, sem advogado, e o registro de mensagens serve como prova. Na prática, para uma mensalidade de aula particular, o custo do seu tempo raramente compensa. O melhor uso dessa perda é ajustar o desenho: pagamento antecipado, e o quarto degrau acontecendo aos quinze dias, não aos noventa.

## O que muda quando a cobrança para de ser manual

O ponto não é a mensagem perfeita. É não depender de você lembrar. Quando o vencimento aparece sozinho na tela, a mensagem sai com o Pix junto e a baixa acontece quando o dinheiro cai, a cobrança deixa de ser uma decisão emocional três vezes por mês e vira o que sempre deveria ter sido: um processo chato e automático.
""",
},

{
    "slug": "como-conseguir-alunos-particulares",
    "categoria": "conseguir-alunos",
    "title": "Como conseguir alunos particulares: 12 canais, do que dá resultado em uma semana ao que leva um ano",
    "seo_title": "Como conseguir alunos particulares: 12 canais que funcionam",
    "dek": "A maioria dos professores tenta o canal mais lento primeiro. Este texto "
           "está em ordem de retorno, do mais rápido ao mais demorado.",
    "seo_description": "12 formas de conseguir alunos particulares em 2026: indicação, "
                       "escolas, marketplaces, redes sociais e o que realmente converte.",
    "keywords": "como conseguir alunos particulares, captar alunos, divulgar aula particular",
    "cta_title": "Já tem interessado? Não perca na hora de agendar",
    "cta_text": "Página pública de agendamento, cadastro do aluno e primeira aula "
                "marcada em dois cliques. O interessado que espera resposta some.",
    "cta_button": "Criar minha página de agendamento",
    "content": """
Professor que precisa de aluno costuma abrir o Instagram e começar a postar. É o canal mais lento de todos, e por isso a sensação é de estar remando sem sair do lugar.

Abaixo estão doze canais em ordem de velocidade de retorno. Comece de cima.

## Retorno em dias

### 1. Os seus ex-alunos

O canal mais subutilizado que existe. Quem teve aula com você e parou já confia em você, já sabe o seu preço e já sabe se gosta do seu jeito.

Faça a lista dos últimos dois anos e mande mensagem individual dizendo que abriu horário. Taxa de resposta de 20 a 40 por cento é normal, e nenhum outro canal chega perto disso.

### 2. Indicação pedida de forma específica

"Indica aí" não gera nada, porque obriga o outro a pensar. Pergunta específica gera:

> "Você conhece alguém no trabalho que precise destravar o inglês para reunião?"

> "Tem alguma mãe na turma do seu filho comentando que o filho está com dificuldade em matemática?"

A diferença é que a segunda versão faz a pessoa procurar uma cara concreta na memória. Ofereça algo em troca: uma aula de bônus por indicação que vira aluno.

### 3. Escolas do bairro, coordenação pedagógica

Escola tem uma fila constante de aluno precisando de reforço e nenhum interesse em dar esse reforço. Coordenador que confia em você indica o ano inteiro.

Vá pessoalmente, leve um material de uma página com o seu nome, a sua formação, as matérias e os horários. Isso é trabalho de uma tarde e costuma render mais que três meses de posts.

## Retorno em semanas

### 4. Grupos de WhatsApp e Facebook do seu bairro

Grupo de condomínio, de mães da escola, de bairro. Não chegue vendendo. Responda dúvidas por algumas semanas e, quando aparecer alguém perguntando por professor, você já é conhecido.

### 5. Marketplaces de aula

Superprof, Profes, Preply e afins entregam volume e cobram caro por isso, em comissão e em preço espremido. Servem para dois usos: encher horário morto e conseguir as primeiras avaliações públicas. Não são lugar para construir a base principal.

### 6. Um perfil que responde à pergunta certa

Quem procura professor faz uma busca específica: "professor de inglês em Curitiba", "aula de matemática para ENEM online". O seu perfil precisa dizer exatamente isso na primeira linha da bio, não "apaixonado por ensinar".

[[cta]]

### 7. Google Meu Negócio

Gratuito, leva vinte minutos e coloca você no mapa de quem busca "professor particular perto de mim". Poucos professores fazem, e é dos poucos canais em que dá para ser primeiro sem gastar nada.

### 8. Parceria com quem atende o mesmo público

Psicopedagoga, fonoaudióloga, professor de outra matéria, dono de escola de música. Todos atendem crianças cujos pais também procuram reforço. Indicação cruzada custa zero e tem confiança embutida.

## Retorno em meses

### 9. Conteúdo curto e útil

Um vídeo de trinta segundos explicando uma dúvida real ("por que se diz *I have been* e não *I am being*") funciona. Foto de citação motivacional não funciona. A régua é simples: o vídeo ensina algo que a pessoa pode usar hoje?

### 10. Aula experimental com formato definido

Aula grátis solta atrai curioso. Um diagnóstico de trinta minutos com devolutiva escrita atrai quem está decidindo. É o mesmo tempo do seu dia, com público diferente.

### 11. Anúncio pago local

Funciona, mas só depois que o resto está de pé: você precisa de um lugar para mandar a pessoa e de resposta rápida. Anúncio que leva para um WhatsApp que responde em seis horas queima dinheiro.

### 12. Autoridade de nicho

O caminho mais lento e o único que muda o seu preço. Ser "professor de inglês" é competir com todo mundo. Ser "quem prepara profissional de TI para entrevista técnica em inglês" é competir com quase ninguém, e permite cobrar o dobro.

## O que estraga todos os doze

Demorar para responder. Interessado em aula particular manda mensagem para três professores no mesmo dia e fecha com quem responde primeiro e propõe um horário concreto.

Responda em até duas horas no horário comercial, sempre com uma pergunta que avança a conversa ("Você prefere terça às 19h ou quinta às 18h?"). Isso vale mais que qualquer estratégia de conteúdo.

E tenha onde receber essa pessoa: um link em que ela vê os seus horários livres e marca sozinha converte muito mais que uma conversa de dezoito mensagens tentando achar um encaixe.
""",
},

{
    "slug": "jogos-para-destravar-o-speaking",
    "categoria": "dicas-de-ingles",
    "title": "10 atividades de 5 minutos para destravar o speaking do aluno travado",
    "seo_title": "10 atividades rápidas para destravar o speaking | Aula de inglês",
    "dek": "Aluno que entende tudo e não fala nada não precisa de mais gramática. "
           "Precisa de tempo de fala com o risco baixo o suficiente para arriscar.",
    "seo_description": "Dez atividades curtas de speaking para aula particular de "
                       "inglês, com instrução pronta, nível e o que fazer com o erro.",
    "keywords": "atividades de speaking, destravar inglês, aula de conversação, warm up inglês",
    "cta_title": "Guarde a atividade que deu certo, no aluno certo",
    "cta_text": "Planejamento por aluno, biblioteca de materiais e histórico do que "
                "já foi usado. Na próxima semana você não recomeça do zero.",
    "cta_button": "Organizar meus materiais",
    "content": """
Aluno travado quase nunca tem problema de vocabulário. Tem medo de errar na frente de alguém que sabe mais. A saída não é explicar melhor: é reduzir o custo do erro e aumentar o tempo de boca aberta.

As dez atividades abaixo cabem em cinco minutos, não precisam de material impresso e funcionam em aula online ou presencial.

## 1. Two truths and a lie

O aluno diz três frases sobre si, duas verdadeiras e uma falsa. Você adivinha qual é a mentira, e faz duas perguntas antes de decidir.

Funciona porque o aluno fala de um assunto que ele domina (a própria vida) e porque adivinhar exige que você faça perguntas, o que dobra o tempo de fala.

**Nível:** A2 em diante.

## 2. A imagem sem contexto

Abra uma foto qualquer e peça três frases: o que está acontecendo, o que aconteceu antes, o que vai acontecer depois.

É o exercício mais econômico que existe para praticar três tempos verbais sem transformar a aula em conjugação.

**Nível:** A2 a B2.

## 3. Um minuto sem parar

Sorteie um tema banal (café da manhã, trânsito, domingo) e peça sessenta segundos ininterruptos. Vale repetir, vale gaguejar, não vale calar.

O objetivo não é falar bonito. É passar por cima do freio que aparece a cada palavra que falta. Cronometre em voz alta: o cronômetro tira a atenção do erro.

**Nível:** B1 em diante. Em A2, use trinta segundos.

## 4. O e-mail impossível

Descreva uma situação: "Você precisa cancelar uma reunião amanhã e o cliente já remarcou duas vezes." O aluno fala em voz alta o que escreveria.

Funciona bem com adulto que estuda para o trabalho, porque a situação é reconhecível e o vocabulário é o que ele realmente vai usar.

**Nível:** B1 em diante.

[[cta]]

## 5. Role-play com carta virada

Você é o atendente, ele é o cliente, e ele não sabe qual problema vai encontrar. Improvise um obstáculo no meio ("o sistema caiu", "acabou o estoque").

O imprevisto é o ponto: fala preparada não treina fala real.

**Nível:** A2 em diante.

## 6. Descreva para quem não vê

O aluno descreve uma imagem, um objeto ou um caminho e você desenha ou executa exatamente o que ele disser, ao pé da letra. Se ele for vago, o resultado sai errado, e ele vê o porquê.

Ensina precisão sem que você precise corrigir nada.

**Nível:** A1 em diante.

## 7. A pergunta de volta

Regra única: em toda resposta, ele devolve uma pergunta. "I had pizza. And you, what did you have?"

Parece bobo e resolve um problema real, o aluno que responde por monossílabo e espera a próxima pergunta cair do céu.

**Nível:** A1 em diante.

## 8. Notícia em três frases

Mande um título de notícia antes da aula. No começo da aula, ele resume em três frases e dá uma opinião.

Vira rotina rápido, e em quatro semanas o aluno já resume qualquer coisa sem travar.

**Nível:** B1 em diante.

## 9. O jogo do "porque"

Toda afirmação precisa vir com uma justificativa. "I don't like winter" sozinha não vale. Com "because it gets dark at five", vale.

Trabalha conectivo, que é exatamente o que separa quem fala por frases soltas de quem sustenta um raciocínio.

**Nível:** A2 em diante.

## 10. Rewind

Grave trinta segundos de fala do aluno, com a permissão dele, e ouçam juntos. Peça que **ele** aponte uma coisa a melhorar antes de você dizer qualquer coisa.

É a atividade mais desconfortável e a que mais gera avanço, porque o aluno percebe sozinho o que a correção externa nunca fixa.

**Nível:** A2 em diante, com o aluno certo. Não use com quem já está inseguro demais.

## Como corrigir sem matar a fluência

Anote os erros e devolva no fim, nunca no meio. Interromper para corrigir uma preposição reforça exatamente o medo que trava o aluno.

No fim da atividade, escolha no máximo três erros para comentar, com este critério:

1. o que atrapalha a compreensão vem primeiro
2. o que se repete várias vezes vem em segundo
3. o resto pode esperar a próxima aula

> Aluno travado não precisa de mais correção. Precisa de mais quilometragem com correção que caiba na cabeça.

## O que fazer com isso na prática

Escolha três destas atividades e use as mesmas por um mês, sempre nos cinco primeiros minutos. Repetição vira ritual, e ritual tira a ansiedade da parte mais difícil da aula.

Anote qual funcionou com qual aluno. O que destrava um adolescente de catorze anos raramente é o que destrava um gerente de quarenta e cinco, e essa memória se perde se ficar só na cabeça.
""",
},

{
    "slug": "planejamento-de-aula-em-15-minutos",
    "categoria": "gestao-da-aula",
    "title": "Planejamento de aula particular: um modelo que cabe em 15 minutos e sobrevive à semana cheia",
    "seo_title": "Planejamento de aula particular: modelo pronto em 15 minutos",
    "dek": "Plano de aula bonito demais não é usado. O que funciona é curto, tem "
           "sempre a mesma estrutura e responde uma pergunta: o que o aluno sai sabendo hoje?",
    "seo_description": "Modelo de planejamento de aula particular em quatro blocos, "
                       "com exemplo pronto e o que fazer quando a aula sai do plano.",
    "keywords": "planejamento de aula particular, plano de aula, modelo de aula",
    "cta_title": "Um plano por aluno, no lugar certo",
    "cta_text": "O EDUCAflowOne guarda o planejamento junto do aluno e da aula, com "
                "os anexos e o histórico. Você abre a aula de terça e o plano está lá.",
    "cta_button": "Testar o planejamento grátis",
    "content": """
Todo professor já montou um plano de aula caprichado, com objetivo, competência e avaliação, usou uma vez e nunca mais. O motivo não é preguiça. É que o formato foi desenhado para escola, com coordenação para prestar contas, e aula particular não tem coordenação: tem um professor cansado às onze da noite decidindo o que fazer amanhã.

O modelo abaixo tem quatro blocos, cabe em meia página e é rápido o bastante para você realmente usar.

## Bloco 1: de onde a gente parou

Duas linhas. O que foi visto na última aula, o que ficou de tarefa, e o que o aluno errou e vale retomar.

Sem esse bloco, os primeiros dez minutos de toda aula viram arqueologia. Com ele, a aula começa andando.

> "Aula passada: past simple com verbos irregulares. Tarefa: 8 frases. Erra sempre 'go' e 'buy'. Retomar no aquecimento."

## Bloco 2: o que ele sai sabendo hoje

Uma frase, começando com um verbo de ação, e no nível do aluno, não do conteúdo:

- ruim: "trabalhar o present perfect"
- bom: "contar uma experiência de viagem usando 'I have been to'"

A diferença importa porque a segunda versão já contém a atividade e já contém como saber se deu certo. A primeira só nomeia um assunto.

Se você não consegue escrever essa frase, a aula ainda não está planejada.

## Bloco 3: os três tempos

Aula particular de 50 a 60 minutos cabe bem em três partes:

| Tempo | O quê | Duração |
| --- | --- | --- |
| Aquecimento | retomar o erro da aula passada, atividade de fala curta | 10 min |
| Núcleo | o objetivo do bloco 2, com prática guiada | 30 min |
| Fechamento | o aluno usa sozinho, tarefa combinada | 10 a 15 min |

O fechamento é o que quase todo mundo corta quando o tempo aperta, e é o mais importante: é o único momento em que dá para ver se ele aprendeu de verdade ou só acompanhou você.

[[cta]]

## Bloco 4: o plano B

Uma linha, com duas saídas:

- **se render antes:** o que fazer com os dez minutos que sobrarem
- **se travar:** onde você recua, geralmente para uma versão mais simples da mesma coisa

Sem plano B, aula que trava vira improviso, e improviso com aluno travado quase sempre vira aula de gramática, que é justamente o que não estava funcionando.

## Um plano inteiro, escrito

> **Aluno:** Camila, B1, terça 19h
> **De onde paramos:** past simple ok. Confunde "been" e "gone".
> **Hoje ela sai sabendo:** contar três experiências de viagem com present perfect, sem confundir been e gone.
> **Aquecimento (10):** um minuto sem parar sobre "a última viagem".
> **Núcleo (30):** contraste been/gone com exemplos dela; 10 frases sobre a própria vida; correção no fim.
> **Fechamento (15):** ela conta uma viagem inteira sem interrupção. Tarefa: áudio de 1 minuto no WhatsApp.
> **Plano B:** se travar, volta para "have you ever...?" em pergunta e resposta.

Isso leva doze minutos para escrever e resolve a aula inteira.

## O que fazer com o plano depois da aula

Duas linhas no fim, ainda com a aula fresca: o que funcionou e o que não funcionou. Esse é o registro que vale ouro três meses depois, quando o aluno pergunta se está evoluindo e você precisa mostrar de onde ele saiu.

## Onde o plano deve morar

No mesmo lugar do aluno. Plano em caderno é perdido, plano em bloco de notas do celular é ilocalizável, plano em pasta do computador não abre quando você está dando aula pelo tablet.

Quando o planejamento fica junto do cadastro do aluno, com o histórico e os materiais anexados, a pergunta "o que a gente estava fazendo mesmo?" desaparece. E o tempo que você gastava reconstruindo isso, toda semana, volta para você.
""",
},

{
    "slug": "whatsapp-aula-particular-sem-virar-refem",
    "categoria": "gestao-da-aula",
    "title": "Aula particular pelo WhatsApp: como usar sem virar refém do celular",
    "seo_title": "WhatsApp para professor particular: como usar sem virar refém",
    "dek": "O WhatsApp é onde o aluno está, e é também onde a sua vida pessoal "
           "acaba. Dá para ficar com a primeira parte sem aceitar a segunda.",
    "seo_description": "Como organizar o WhatsApp da aula particular: horário de "
                       "atendimento, mensagens prontas, separação de conta e cobrança.",
    "keywords": "whatsapp professor particular, atender aluno whatsapp, organizar mensagens aluno",
    "cta_title": "Cobrança e aviso no WhatsApp, sem você digitar",
    "cta_text": "O EDUCAflowOne conversa com o WhatsApp do aluno: lembrete de aula, "
                "cobrança com Pix junto e baixa automática quando o pagamento cai.",
    "cta_button": "Ver como funciona",
    "content": """
Nenhum professor particular no Brasil vai convencer o aluno a baixar um aplicativo para falar com ele. A conversa acontece no WhatsApp, e vai continuar acontecendo lá.

O problema não é o canal. É que ele chega junto com a mensagem da tia, a conta de luz e o grupo do prédio, às onze da noite, no mesmo lugar.

## Regra 1: separe a conta

WhatsApp Business é gratuito e resolve metade do problema sozinho. Ele permite:

- um perfil com o seu horário de atendimento visível
- mensagem automática de ausência fora do horário
- mensagem de saudação para quem chega pela primeira vez
- etiquetas para separar interessado, aluno ativo e devedor
- respostas rápidas, que evitam redigitar a mesma explicação pela quadragésima vez

Se der para usar um número separado, melhor ainda. Um chip pré-pago barato compra de volta o seu domingo.

## Regra 2: horário de atendimento existe e é dito

Escreva no perfil e diga na primeira conversa: "Respondo mensagens de segunda a sexta, das 9h às 19h."

Ninguém se ofende com isso. O que gera ressentimento é o contrário: você responder às 23h por três meses e, no quarto, se irritar com uma mensagem às 23h. A expectativa foi você que criou.

Se responder fora do horário for inevitável, programe o envio. O aluno não precisa saber que você escreveu de madrugada.

## Regra 3: mensagem pronta para as cinco conversas repetidas

Todo professor tem as mesmas cinco conversas, o ano inteiro:

1. quanto custa e como funciona
2. confirmação da aula
3. cancelamento e remarcação
4. lembrete de pagamento
5. tarefa e material

Escreva as cinco uma vez, bem escritas, e salve como resposta rápida. Você vai economizar horas e, mais importante, vai parar de escrever mal a mensagem difícil quando estiver cansado.

[[cta]]

## Regra 4: confirmação é combinada, não improvisada

Mande a confirmação sempre no mesmo momento, por exemplo às 18h do dia anterior, com o mesmo texto:

> "Oi, Pedro! Confirmando nossa aula amanhã, quinta, às 19h. Até lá!"

Duas linhas que derrubam falta e reduzem o remarque de última hora. E, quando é sempre no mesmo horário, o aluno passa a esperar e a avisar antes.

## Regra 5: dinheiro na mesma conversa, mas nunca no meio da aula

Cobrança por WhatsApp funciona bem quando tem três coisas: valor, referência do período e a chave Pix na mesma mensagem, para a pessoa resolver com dois toques.

O que não funciona é falar de dinheiro durante o horário da aula ou logo depois de uma aula difícil. Escolha um horário do dia para tratar de pagamento, e trate de todos de uma vez.

## Regra 6: o que não pode viver só no WhatsApp

Conversa é ótimo canal de recado e péssimo arquivo. Estas quatro coisas precisam morar em outro lugar:

- **quanto cada aluno pagou e quando**: rolar dez mil mensagens atrás de um comprovante é a definição de tempo perdido
- **o histórico do que foi ensinado**: no fim do semestre, você precisa saber o caminho, não achar um áudio
- **materiais**: PDF enviado em março some da vista em abril
- **a agenda**: aula combinada em conversa e não anotada é aula esquecida

O WhatsApp continua sendo a porta. Ele só não pode ser o armário.

## Regra 7: um lugar para o interessado que ainda não é aluno

A pior perda acontece antes do aluno existir: alguém pergunta o preço, você demora quatro horas, e a pessoa já fechou com outro.

Ter um link com os seus horários livres, em que a pessoa marca sozinha uma aula de diagnóstico, resolve isso mesmo quando você está dando aula e não pode responder.

## O resultado prático

Nada disso é sobre tecnologia. É sobre devolver duas coisas: a noite, que hoje é interrompida por mensagem de cobrança e remarcação, e a memória, que hoje está espalhada em conversas que ninguém consegue pesquisar.

O WhatsApp continua. Só deixa de ser o único lugar onde o seu trabalho existe.
""",
},

{
    "slug": "present-perfect-como-explicar-para-brasileiro",
    "categoria": "dicas-de-ingles",
    "title": "Present perfect: como explicar para brasileiro sem enrolação (e por que a tradução atrapalha)",
    "seo_title": "Present perfect: como explicar para brasileiro | Aula de inglês",
    "dek": "O aluno brasileiro não erra o present perfect por falta de regra. "
           "Erra porque a regra que ele decorou tenta traduzir o que não tem tradução.",
    "seo_description": "Como ensinar present perfect para alunos brasileiros: a "
                       "explicação que funciona, os quatro usos, erros comuns e atividades.",
    "keywords": "present perfect, como ensinar present perfect, inglês para brasileiros",
    "cta_title": "Guarde esta aula e reaproveite no próximo aluno",
    "cta_text": "Planejamento por aluno, biblioteca de materiais e histórico de aulas. "
                "O que você preparou uma vez fica pronto para a próxima turma.",
    "cta_button": "Organizar meu material",
    "content": """
Se existe um assunto que volta em toda aula de inglês intermediário, é este. E quase sempre volta porque a primeira explicação que o aluno recebeu foi "é o nosso pretérito perfeito composto", o que é falso e cria um problema que leva anos para desfazer.

## Por que a tradução quebra

Em português, "eu tenho estudado" significa uma ação repetida num período recente. Em inglês, *I have studied* faz outra coisa: liga um fato passado ao momento presente, sem dizer quando o fato aconteceu.

O aluno que traduz produz frases como *I have studied yesterday*, que soa errada por um motivo que ele não consegue enxergar: o present perfect e um momento fechado no passado não convivem, porque um olha para o agora e o outro fecha a porta.

## A explicação que funciona: a linha do tempo com uma porta

Desenhe uma linha. Marque o "agora" na ponta direita.

- **Past simple**: um ponto no passado, com uma porta fechada em volta. Terminou, o período acabou, ninguém mexe mais. *I saw that film in 2019.*
- **Present perfect**: uma seta que sai do passado e chega até o agora, sem ponto marcado. O período ainda está aberto. *I have seen that film.*

A pergunta que resolve 80 por cento dos casos é uma só: **o período de tempo já fechou?**

- "ontem", "em 2019", "na semana passada": fechou. Past simple.
- "hoje", "esta semana", "na minha vida", "desde 2019": ainda está aberto. Present perfect.

Repare que nem apareceu a palavra "tradução".

## Os quatro usos, em ordem de utilidade

### 1. Experiência de vida

*I have been to Chile.* O que importa é que aconteceu alguma vez, não quando.

É o uso mais fácil de mostrar e o melhor ponto de partida, porque o aluno tem material de sobra: a própria vida.

### 2. Resultado que ainda vale agora

*I have lost my keys.* A chave continua perdida. Se ela aparecesse, a frase deixaria de fazer sentido.

Este é o uso que o brasileiro mais estranha, e o mais frequente na fala real.

### 3. Algo que começou no passado e continua

*I have lived here for ten years.* Continuo morando.

Aqui entram *for* e *since*, e vale gastar tempo: *for* mede duração (*for ten years*), *since* marca o começo (*since 2016*).

### 4. Passado muito recente com *just*, *already*, *yet*

*I have just finished.* *Have you eaten yet?*

[[cta]]

## Os cinco erros que todo aluno brasileiro comete

**1. Present perfect com tempo fechado.** *I have travelled last year.* Corrija sempre pela pergunta do período, nunca pela regra decorada.

**2. Confundir been e gone.** *He has been to Paris* (foi e voltou). *He has gone to Paris* (foi e está lá). Um exemplo com a pessoa presente ou ausente na sala resolve em trinta segundos.

**3. Usar present simple para duração.** *I live here for ten years* é o erro mais teimoso que existe, porque em português é assim mesmo. Trate como falso amigo estrutural e volte a ele várias vezes.

**4. Perguntar *Did you ever...?* querendo experiência de vida.** Não está errado no inglês americano falado, e vale dizer isso ao aluno, mas em prova ele precisa de *Have you ever...?*

**5. Traduzir *have* como "ter posse".** *I have eaten* não tem nada a ver com possuir. Se o aluno insiste, mostre que *have* aqui é peça de estrutura, do mesmo jeito que "vou" em "vou comer" não é ir a lugar nenhum.

## Uma sequência de aula pronta

1. **Aquecimento (5 min):** três perguntas de experiência sobre a vida dele. *Have you ever eaten sushi? Have you ever driven a motorcycle?*
2. **Descoberta (10 min):** escreva duas frases lado a lado, *I went to Chile in 2019* e *I have been to Chile*, e peça que ele explique a diferença. Não dê a resposta antes de ele tentar.
3. **Regra (5 min):** a linha do tempo e a pergunta do período fechado. Cinco minutos, nem um a mais.
4. **Prática guiada (15 min):** dez frases sobre a vida dele, metade past simple, metade present perfect, escolhendo qual usar.
5. **Uso livre (15 min):** ele conta a própria história em três frases usando os dois tempos, e você anota os erros para o fim.
6. **Tarefa:** um áudio de um minuto respondendo "what have you done this week?".

## O teste de que ele entendeu

Não é acertar exercício de completar lacuna. É conseguir explicar, com as próprias palavras, por que *I have finished my homework yesterday* está errada.

Quem consegue explicar, aprendeu. Quem só acerta a lacuna, decorou, e vai errar de novo em três semanas.
""",
},

]
