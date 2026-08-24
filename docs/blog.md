# Blog do EDUCAflowOne

Páginas públicas em `/blog/`, fora da landing. A landing só aponta para cá, pelo
menu, pelo menu do celular e pelo rodapé.

Existe por um motivo comercial: o professor procura no Google "quanto cobrar por
aula particular", cai num artigo nosso, e encontra o convite de cadastro no meio
do texto. Todo artigo publicado tem três convites, e todos levam para `/signup/`,
que já oferece entrar com a conta Google.

## Onde fica cada coisa

| Ficheiro | O que faz |
| --- | --- |
| `core/models.py` | `BlogCategory` e `BlogPost`, no fim do ficheiro |
| `core/blog_views.py` | lista, artigo, categoria, RSS, `sitemap.xml`, `robots.txt` |
| `core/blog_markdown.py` | converte o texto do artigo em HTML, sem dependência externa |
| `core/blog_schedule.py` | a fila: converte "2 por dia às 9h e 17h30" em datas |
| `core/blog_seed_content.py` | os oito artigos de lançamento |
| `core/templatetags/blog_tags.py` | datas em português e no fuso de Brasília |
| `frontend/templates/blog/` | `base.html`, `index.html`, `post.html`, `_cta.html` |
| `core/tests_blog.py` | 32 testes |
| `core/migrations/0060_blog.py` | escrita à mão, ver a nota no fim |

## Publicar um artigo

Pelo `/admin/` > Artigos do blog > Adicionar.

O corpo é Markdown, e só estas marcas funcionam:

```
## Título de seção          ### Subtítulo
- lista                     1. lista numerada
> caixa de destaque         ---  (linha)
**negrito**  *itálico*  [texto](/link/)
| tabela | com |
| --- | --- |
| duas | colunas |
![descrição](url da imagem)
[[cta]]   <- onde entra o convite de cadastro
```

Sem `[[cta]]`, o convite entra sozinho antes do segundo `## título`. O convite do
fim do artigo e o da coluna lateral aparecem sempre.

O sumário "Neste artigo" aparece sozinho quando existem três ou mais `##`.

## Agendar: uma ou duas postagens por dia

**Não existe cron, nem worker, nem tarefa periódica.** Um artigo com status
*Publicado* e data futura simplesmente não passa pelo filtro da consulta. Quando
o relógio passa da data, passa a passar. Não há nada que possa falhar de
madrugada e deixar o dia sem artigo.

Três formas de pôr na fila:

**No admin, um a um:** status *Publicado* e data futura. Atenção: o campo de data
do admin está em UTC, três horas à frente de Brasília. Para sair às 9h, grave 12:00.

**No admin, em lote:** selecione os rascunhos na lista e use a ação
*Agendar: 1 por dia* ou *Agendar: 2 por dia*. Estas já fazem a conta do fuso.

**Pela linha de comando:**

```bash
.venv/Scripts/python.exe dev_local.py blog_agenda
```

Sem argumentos é só relatório: o que está no ar, o que sai nos próximos dias,
quantos rascunhos existem. Para encher a fila:

```bash
.venv/Scripts/python.exe dev_local.py blog_agenda --por-dia 2
```

Outras opções: `--inicio 2026-09-01` para escolher o primeiro dia, `--domingo`
para usar domingo também (por omissão a fila pula domingo), `--limpar` para tirar
tudo da fila e devolver a rascunho.

Horários da fila, no fuso de Brasília: uma por dia sai às 9h; duas por dia saem
às 9h e às 17h30. Para mudar, é o `HORARIOS_PADRAO` em `core/blog_schedule.py`.

## Os oito artigos de lançamento

```bash
.venv/Scripts/python.exe dev_local.py blog_seed --publicar-agora 2 --agendar 2
```

Cria as cinco editorias (Volta às aulas, Dicas de inglês, Gestão da aula,
Dinheiro e cobrança, Conseguir alunos), publica os dois primeiros artigos e põe
os outros seis na fila, dois por dia.

O comando é idempotente por slug: rodar de novo não duplica nada e nunca
sobrescreve texto já editado no admin. Para acrescentar artigos novos ao lote,
copie um dicionário em `core/blog_seed_content.py`, mude o slug, e rode de novo.

## Pré-visualizar antes da hora

Estando logado como administrador, `/blog/<slug>/` abre rascunho e agendado, com
um aviso amarelo no topo e cabeçalho `X-Robots-Tag: noindex`. Para todos os
outros, é 404: artigo agendado não vaza na lista, nem no RSS, nem no sitemap,
nem por URL direta.

## O que o Google recebe

- `sitemap.xml` e `robots.txt`, servidos pela aplicação
- `<link rel=canonical>` em toda página
- JSON-LD `BlogPosting` e `BreadcrumbList` no artigo, `Blog` na lista
- Open Graph e Twitter Card, para o link colado no WhatsApp virar cartão
- RSS em `/blog/rss/`
- `robots.txt` fecha `/dashboard/`, `/calendar/`, `/alunos/` e o resto da área do
  cliente, que só devolvem redirecionamento de login e gastariam orçamento de
  rastreio à toa

Depois do primeiro deploy, cadastre `https://www.educaflowone.com.br/sitemap.xml`
no Google Search Console. Sem isso, a indexação leva semanas em vez de dias.

## Medir o que o blog traz

Todo botão de convite carrega `utm_source=blog`, `utm_medium` (onde estava o
botão: `topo`, `meio-do-artigo`, `fim-do-artigo`, `lateral`, `rodape`, `menu`) e
`utm_campaign` com o slug do artigo. O Meta Pixel da landing já roda nas páginas
do blog, então dá para ver a origem sem instalar mais nada.

## Duas notas de manutenção

**A migração `0060_blog.py` foi escrita à mão.** No momento em que o blog foi
construído havia outra alteração de modelo em curso na mesma árvore (o
`public_token` do Pix, que virou a `0061`). Rodar `makemigrations` teria arrastado
essa alteração pela metade para dentro da migração do blog. O índice do modelo
tem nome explícito (`blog_status_data_idx`) exatamente para o modelo e a migração
não discordarem depois.

**As datas do blog não usam o locale do Django.** O projeto roda com
`LANGUAGE_CODE = en-us` e `TIME_ZONE = UTC`, e mexer nisso mudaria a hora que
aparece na agenda de quem já usa o sistema. Os filtros em
`core/templatetags/blog_tags.py` convertem para Brasília e escrevem o mês em
português só nas páginas do blog.
