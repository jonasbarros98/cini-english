"""
Blog público: listagem, artigo, categoria, RSS, sitemap e robots.

Tudo aqui é aberto, sem sessão, e propositalmente barato de servir: quem chega
por busca do Google não tem conta, não tem cookie, e desiste se a página demora.

Regra de visibilidade, uma só, em `BlogPost.objects.published()`: status
publicado E data de publicação já vencida. Quem está na fila (data futura) não
aparece em lugar nenhum, nem na lista, nem no RSS, nem no sitemap, nem por URL
direta. Não há tarefa periódica: o artigo entra no ar sozinho quando o relógio
passa da data marcada.

Exceção deliberada: um administrador logado consegue abrir rascunho e agendado
pela URL direta, para revisar antes da hora. A página avisa, e o cabeçalho
manda o robô não indexar.
"""

from django.contrib.syndication.views import Feed
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils.feedgenerator import Rss201rev2Feed
from django.views.generic import View

from .blog_markdown import CTA_TOKEN
from .models import BlogCategory, BlogPost

POR_PAGINA = 9

# Origem das visitas que o blog empurra para o cadastro. Fica aqui, num sítio
# só, porque a leitura destes parâmetros no Meta Pixel depende de eles serem
# sempre os mesmos.
UTM_BASE = "utm_source=blog&utm_medium=artigo"


def _pode_ver_rascunho(request) -> bool:
    return bool(request.user.is_authenticated and request.user.is_staff)


def _contexto_base(request):
    return {
        "categorias": BlogCategory.objects.all(),
        "canonical": request.build_absolute_uri(request.path),
    }


class BlogIndexView(View):
    """
    /blog/ e /blog/categoria/<slug>/

    Aceita ?q= para busca e ?page= para paginação. A busca é `icontains` em
    título, linha de apoio e corpo: com dezenas de artigos isso resolve, e
    poupa a este projeto uma dependência de busca textual.
    """

    def get(self, request, categoria=None):
        posts = BlogPost.objects.published().select_related("category")

        cat = None
        if categoria:
            cat = get_object_or_404(BlogCategory, slug=categoria)
            posts = posts.filter(category=cat)

        busca = (request.GET.get("q") or "").strip()
        if busca:
            posts = posts.filter(
                Q(title__icontains=busca)
                | Q(dek__icontains=busca)
                | Q(content__icontains=busca)
                | Q(keywords__icontains=busca)
            )

        # O destaque só abre a primeira página da lista completa: numa busca ou
        # dentro de uma categoria, o leitor quer a lista, não a nossa curadoria.
        destaque = None
        if not busca and not cat and request.GET.get("page") in (None, "", "1"):
            destaque = posts.filter(featured=True).first() or posts.first()
            if destaque:
                posts = posts.exclude(pk=destaque.pk)

        pagina = Paginator(posts, POR_PAGINA).get_page(request.GET.get("page"))

        ctx = _contexto_base(request)
        ctx.update({
            "posts": pagina,
            "destaque": destaque,
            "categoria_atual": cat,
            "busca": busca,
            "total": posts.count(),
            "titulo_pagina": (
                f"{cat.name}: artigos para professores" if cat
                else "Blog do EDUCAflowOne: gestão para quem dá aula particular"
            ),
            "descricao_pagina": (
                cat.description if cat and cat.description
                else "Preço de aula, agenda, cobrança, planejamento e captação de "
                     "alunos. Conteúdo prático para professor particular e escola pequena."
            ),
        })
        return render(request, "blog/index.html", ctx)


class BlogPostView(View):
    """/blog/<slug>/"""

    def get(self, request, slug):
        post = get_object_or_404(
            BlogPost.objects.select_related("category"), slug=slug
        )
        if not post.is_published and not _pode_ver_rascunho(request):
            raise Http404("Artigo não encontrado")

        # F() em vez de post.views += 1: dois leitores ao mesmo tempo não podem
        # gravar o mesmo número. Não conta quem é da casa.
        if post.is_published and not _pode_ver_rascunho(request):
            BlogPost.objects.filter(pk=post.pk).update(views=F("views") + 1)

        # O corpo chega com uma sentinela onde entra o convite de cadastro.
        # Partir aqui, e não no template, evita ter de marcar HTML como seguro
        # duas vezes e deixa o bloco de CTA ser um include normal.
        blocos = post.render_html().split(CTA_TOKEN)

        ctx = _contexto_base(request)
        ctx.update({
            "post": post,
            "blocos": blocos,
            "sumario": post.sumario(),
            "relacionados": post.relacionados(),
            "previa": not post.is_published,
            "utm": f"{UTM_BASE}&utm_campaign={post.slug}",
        })
        resposta = render(request, "blog/post.html", ctx)
        if not post.is_published:
            resposta["X-Robots-Tag"] = "noindex, nofollow"
        return resposta


class BlogFeed(Feed):
    """RSS em /blog/rss/. Barato de manter e ainda é como agregadores leem."""

    feed_type = Rss201rev2Feed
    title = "Blog do EDUCAflowOne"
    link = "/blog/"
    description = (
        "Gestão, cobrança, agenda e captação de alunos para professores particulares."
    )
    language = "pt-br"

    def items(self):
        return BlogPost.objects.published().select_related("category")[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.resumo

    def item_link(self, item):
        return item.get_absolute_url()

    def item_pubdate(self, item):
        return item.published_at

    def item_categories(self, item):
        return [item.category.name] if item.category_id else []


def sitemap_xml(request):
    """
    Sitemap escrito à mão, sem django.contrib.sitemaps.

    O framework de sitemaps traria django.contrib.sites junto (ou uma dança com
    RequestSite) para resolver o domínio, e o domínio aqui já vem certo do
    request: o Railway envia X-Forwarded-Proto e o settings confia nele.
    """
    base = request.build_absolute_uri("/").rstrip("/")

    urls = [
        (base + "/", "1.0", "weekly", None),
        (base + reverse("planos"), "0.8", "monthly", None),
        (base + "/blog/", "0.9", "daily", None),
    ]
    for cat in BlogCategory.objects.all():
        urls.append((base + cat.get_absolute_url(), "0.5", "weekly", None))
    for post in BlogPost.objects.published():
        urls.append((
            base + post.get_absolute_url(),
            "0.7",
            "monthly",
            (post.updated_at or post.published_at),
        ))
    for nome in ("privacidade", "termos", "exclusao-de-dados"):
        urls.append((base + reverse(nome), "0.2", "yearly", None))

    linhas = ['<?xml version="1.0" encoding="UTF-8"?>',
              '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for loc, prio, freq, mod in urls:
        linhas.append("<url>")
        linhas.append(f"<loc>{loc}</loc>")
        if mod:
            linhas.append(f"<lastmod>{mod.date().isoformat()}</lastmod>")
        linhas.append(f"<changefreq>{freq}</changefreq>")
        linhas.append(f"<priority>{prio}</priority>")
        linhas.append("</url>")
    linhas.append("</urlset>")

    return HttpResponse("\n".join(linhas), content_type="application/xml")


def robots_txt(request):
    """
    Libera o que é público e fecha o que é área de trabalho de cliente pagante.

    Sem isto, o Google gasta orçamento de rastreio em /dashboard/ e /calendar/,
    que respondem redirecionamento de login e não valem uma linha de índice.
    """
    base = request.build_absolute_uri("/").rstrip("/")
    linhas = [
        "User-agent: *",
        "Allow: /$",
        "Allow: /blog/",
        "Allow: /planos/",
        "Disallow: /admin/",
        "Disallow: /api/",
        "Disallow: /dashboard/",
        "Disallow: /calendar/",
        "Disallow: /alunos/",
        "Disallow: /financeiro/",
        "Disallow: /arquivos/",
        "Disallow: /planejamento/",
        "Disallow: /whatsapp/",
        "Disallow: /perfil/",
        "Disallow: /aluno/",
        "Disallow: /agendar/",
        "Disallow: /recibo/",
        "Disallow: /painel-admin/",
        "Disallow: /previa-8t3kqz/",
        "",
        f"Sitemap: {base}/sitemap.xml",
    ]
    return HttpResponse("\n".join(linhas), content_type="text/plain; charset=utf-8")
