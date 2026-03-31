# Email de anuncio — Arquivos (Biblioteca do Professor)

**Tipo:** Lifecycle — anuncio de nova funcionalidade
**Produto:** EducaflowOne
**Funcionalidade:** Arquivos (`/arquivos/`)
**Idioma:** PT-BR
**Status:** Pronto para revisao e envio
**Criado em:** 2026-03-25

---

## Linhas de assunto (opcoes A/B/C)

| Opcao | Assunto |
|-------|---------|
| **A** | Chega de procurar PDF no WhatsApp |
| **B** | Seus materiais de ensino, todos em um so lugar |
| **C** | Novo no EducaflowOne: uma biblioteca so sua |

> Recomendacao de teste: rodar A vs. B. A e mais direta na dor; B e mais orientada ao beneficio. C funciona como fallback mais neutro se a base for menos homogenea em relacao ao habito de guardar arquivos no WhatsApp.

---

## Preview text (pre-header)

> Faca upload uma vez. Envie para qualquer aluno, quando quiser — direto pelo EducaflowOne.

*(Limite recomendado: 85 caracteres. Este texto tem 84.)*

---

## Corpo do email

---

**De:** EducaflowOne `<ola@educaflowone.com>` *(ou alias configurado)*
**Para:** `{{first_name}}` — segmento de professores ativos pagantes, nao parceiros

---

Oi, **{{first_name}}** —

Voce ja perdeu tempo procurando aquele PDF que mandou para um aluno no mes passado?

Faz parte da rotina de quase todo professor particular: o material esta no Drive, ou no WhatsApp, ou na pasta do notebook, ou — quem sabe — nos tres ao mesmo tempo. Na hora de reusar, voce baixa, procura o aluno certo, reenvia. De novo.

Criamos o **Arquivos** para acabar com isso.

---

**Sua biblioteca de materiais, dentro do EducaflowOne.**

Agora voce tem um espaco so seu para guardar PDFs, audios, videos, imagens, documentos e ate links externos — tudo organizado com busca, filtros e tags, no mesmo lugar onde voce ja gerencia seus alunos e agenda.

Sem nova aba aberta. Sem nova assinatura.

**O que voce pode fazer:**

- **Subir uma vez, usar sempre** — faca o upload do seu material e reuse com quantos alunos quiser, sem precisar localizar o arquivo no seu computador de novo.
- **Encontrar rapido** — busca por nome, filtre por tipo (PDF, audio, video...) ou por tag. Antes de aula, sem correria.
- **Enviar direto para o aluno** — com um clique, o arquivo vai para a area do aluno especifico dentro do portal. Nao e um link do Drive. Nao e uma mensagem no WhatsApp. E um registro organizado, no lugar certo, para ele acessar quando precisar.

---

**Quanto espaco voce tem?**

Depende do seu plano atual:

| Plano | Tamanho maximo por arquivo | Total da biblioteca |
|-------|---------------------------|---------------------|
| Basic | 10 MB | 100 MB / ate 50 arquivos |
| Premium | 20 MB | 500 MB / ate 200 arquivos |
| Platinum | 50 MB | ~2 GB / sem limite de quantidade |

Voce esta no plano **{{plan_name}}**. O indicador de uso aparece direto na tela do Arquivos — sem surpresa na hora de subir um arquivo novo.

---

**Experimente agora.**

Acesse o Arquivos, suba tres materiais que voce mais reutiliza e envie um para um aluno. Leva menos de dois minutos.

**[Abrir meus Arquivos →](https://educaflowone.com/arquivos/)**

---

Qualquer duvida, e so responder este email.

Bons estudos para os seus alunos,
**Equipe EducaflowOne**

---

*Voce esta recebendo este email porque tem uma conta ativa no EducaflowOne. Para gerenciar suas preferencias de comunicacao, [clique aqui](#).*

---

## Tokens de personalizacao

| Token | Descricao | Obrigatorio |
|-------|-----------|-------------|
| `{{first_name}}` | Primeiro nome do professor | Sim — personaliza saudacao e chamada inicial |
| `{{plan_name}}` | Nome do plano atual (Basic, Premium ou Platinum) | Sim — contextualiza a tabela de limites sem parecer generico |

> Se `{{plan_name}}` nao estiver disponivel na camada de envio, remova a frase "Voce esta no plano **{{plan_name}}**." e mantenha a tabela como referencia geral. Nao invente o plano.

> Se `{{first_name}}` nao estiver disponivel, substitua a saudacao por "Oi, professor —" ou "Ola —".

---

## Nota de envio

**Quem recebe:**
- Professores com conta ativa e plano pago (Basic, Premium ou Platinum).
- Professores em periodo de trial com acesso ativo (limite equivalente ao Basic — a tabela ja reflete isso implicitamente).

**Quem NAO recebe (guardrail obrigatorio):**
- Contas configuradas como **professor parceiro** (`partner mode`). O Arquivos e bloqueado para esse perfil via API (403). Enviar o email para parceiros geraria expectativa de uma funcionalidade que eles nao podem usar. Segmentar ou excluir antes do envio.

**Horario sugerido de envio:**
- Terca ou quarta-feira, entre 9h e 11h (horario de Brasilia).
- Evitar segunda de manha (sobrecarga de inbox) e sexta a tarde (baixo engajamento).
- Professores particulares tendem a checar email fora de horario de aula — o intervalo da manha funciona bem antes das aulas do dia comecar.

**Volume e frequencia:**
- Envio unico de anuncio. Nao repetir para quem ja abriu ou clicou.
- Considerar reenvio 5-7 dias depois somente para quem nao abriu, com assunto alternativo (opcao B ou C acima).

---

*Fonte de verdade: `docs/educaflow-marketing-specialist/feature-arquivos-teacher-library.md` — alinhado com limites de plano e guardrails de parceiros documentados em 2026-03-25.*
