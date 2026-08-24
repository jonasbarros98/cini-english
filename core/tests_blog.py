"""
Testes do blog.

Três coisas aqui não podem quebrar nunca, porque quebradas custam dinheiro:

1. Artigo agendado não pode vazar antes da hora, nem na lista, nem no RSS,
   nem no sitemap, nem por URL direta.
2. Todo artigo publicado tem que ter o convite de cadastro, com a origem
   marcada. Blog sem CTA é blog que não traz assinante.
3. Texto de artigo não vira HTML executável. Quem escreve é gente de casa,
   mas texto colado de outro lugar não pode injetar script na página pública.
"""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from .blog_markdown import CTA_TOKEN, auto_cta, plain_excerpt, reading_minutes, render
from .blog_schedule import TZ_BR, gerar_datas
from .models import BlogCategory, BlogPost


def criar_post(**kwargs):
    dados = {
        "title": "Como cobrar aula particular",
        "content": "## Um\n\nTexto do artigo.\n\n## Dois\n\nMais texto.\n\n## Três\n\nFim.",
        "status": BlogPost.STATUS_PUBLISHED,
        "published_at": timezone.now() - timedelta(days=1),
    }
    dados.update(kwargs)
    return BlogPost.objects.create(**dados)


class MarkdownTests(TestCase):

    def test_converte_as_marcas_que_o_blog_usa(self):
        html, _ = render(
            "## Título\n\nTexto **forte** e *leve*.\n\n- um\n- dois\n\n"
            "1. passo\n\n> destaque\n\n| A | B |\n| --- | --- |\n| 1 | 2 |"
        )
        for pedaco in ("<h2", "<strong>forte</strong>", "<em>leve</em>", "<ul>",
                       "<ol>", "<blockquote>", "<table>"):
            self.assertIn(pedaco, html)

    def test_nao_deixa_passar_html_do_texto(self):
        html, _ = render("Olha isto: <script>alert(1)</script> e <img onerror=x>")
        self.assertNotIn("<script>", html)
        self.assertNotIn("<img onerror", html)
        self.assertIn("&lt;script&gt;", html)

    def test_link_externo_ganha_rel_seguro_e_interno_nao(self):
        html, _ = render("[fora](https://exemplo.com) e [dentro](/planos/)")
        self.assertIn('rel="noopener noreferrer"', html)
        self.assertIn('<a href="/planos/">dentro</a>', html)

    def test_titulos_viram_ancoras_unicas(self):
        html, toc = render("## Preço\n\nx\n\n## Preço\n\ny")
        self.assertEqual([t["id"] for t in toc], ["preco", "preco-2"])
        self.assertIn('id="preco-2"', html)

    def test_cta_do_autor_ganha_do_automatico(self):
        html, _ = render("## A\n\nx\n\n[[cta]]\n\n## B\n\ny\n\n## C\n\nz")
        self.assertEqual(html.count(CTA_TOKEN), 1)
        # Marcado depois do primeiro título, e não antes do segundo.
        self.assertLess(html.find(CTA_TOKEN), html.find("<h2 id=\"b\""))
        self.assertEqual(auto_cta(html).count(CTA_TOKEN), 1)

    def test_cta_automatico_entra_antes_do_segundo_titulo(self):
        html, _ = render("## A\n\nx\n\n## B\n\ny")
        self.assertNotIn(CTA_TOKEN, html)
        com_cta = auto_cta(html)
        self.assertEqual(com_cta.count(CTA_TOKEN), 1)
        self.assertLess(com_cta.find(CTA_TOKEN), com_cta.find('<h2 id="b"'))

    def test_minutos_e_resumo(self):
        self.assertEqual(reading_minutes("palavra " * 400), 2)
        self.assertEqual(reading_minutes(""), 1)
        self.assertEqual(plain_excerpt("## Título\n\nO primeiro parágrafo."), "O primeiro parágrafo.")


class AgendamentoTests(TestCase):

    def test_uma_por_dia_sai_de_manha_no_fuso_de_brasilia(self):
        datas = gerar_datas(3, por_dia=1, inicio=None, pular_domingo=False)
        self.assertEqual(len(datas), 3)
        for d in datas:
            self.assertEqual(d.astimezone(TZ_BR).hour, 9)
        # um dia de diferença entre cada
        self.assertEqual((datas[1] - datas[0]).days, 1)

    def test_duas_por_dia_ocupam_manha_e_fim_de_tarde_do_mesmo_dia(self):
        datas = gerar_datas(4, por_dia=2, pular_domingo=False)
        locais = [d.astimezone(TZ_BR) for d in datas]
        self.assertEqual(locais[0].date(), locais[1].date())
        self.assertEqual(locais[0].hour, 9)
        self.assertEqual(locais[1].hour, 17)
        self.assertEqual(locais[2].date(), locais[0].date() + timedelta(days=1))

    def test_fila_pula_domingo(self):
        datas = gerar_datas(10, por_dia=1, pular_domingo=True)
        self.assertNotIn(6, [d.astimezone(TZ_BR).weekday() for d in datas])


class VisibilidadeTests(TestCase):
    """A regra que não pode falhar: agendado é invisível até a hora."""

    def setUp(self):
        self.no_ar = criar_post(title="Já publicado", slug="ja-publicado")
        self.agendado = criar_post(
            title="Sai amanhã", slug="sai-amanha",
            published_at=timezone.now() + timedelta(days=1),
        )
        self.rascunho = criar_post(
            title="Rascunho", slug="rascunho",
            status=BlogPost.STATUS_DRAFT, published_at=None,
        )

    def test_consulta_de_publicados_so_traz_o_que_ja_venceu(self):
        self.assertEqual(list(BlogPost.objects.published()), [self.no_ar])
        self.assertEqual(list(BlogPost.objects.scheduled()), [self.agendado])

    def test_lista_nao_mostra_agendado_nem_rascunho(self):
        html = self.client.get("/blog/").content.decode()
        self.assertIn("Já publicado", html)
        self.assertNotIn("Sai amanhã", html)
        self.assertNotIn("Rascunho", html)

    def test_url_direta_de_agendado_da_404_para_visitante(self):
        self.assertEqual(self.client.get("/blog/sai-amanha/").status_code, 404)
        self.assertEqual(self.client.get("/blog/rascunho/").status_code, 404)

    def test_administrador_ve_a_previa_e_o_robo_nao(self):
        User.objects.create_superuser("chefe", "chefe@x.com", "x")
        self.client.login(username="chefe", password="x")
        r = self.client.get("/blog/sai-amanha/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["X-Robots-Tag"], "noindex, nofollow")
        self.assertIn("Pré-visualização", r.content.decode())

    def test_agendado_nao_entra_no_sitemap_nem_no_rss(self):
        sitemap = self.client.get("/sitemap.xml").content.decode()
        self.assertIn("/blog/ja-publicado/", sitemap)
        self.assertNotIn("/blog/sai-amanha/", sitemap)

        rss = self.client.get("/blog/rss/").content.decode()
        self.assertIn("Já publicado", rss)
        self.assertNotIn("Sai amanhã", rss)

    def test_visita_de_administrador_nao_conta_leitura(self):
        User.objects.create_superuser("chefe", "chefe@x.com", "x")
        self.client.login(username="chefe", password="x")
        self.client.get("/blog/ja-publicado/")
        self.no_ar.refresh_from_db()
        self.assertEqual(self.no_ar.views, 0)

        self.client.logout()
        self.client.get("/blog/ja-publicado/")
        self.no_ar.refresh_from_db()
        self.assertEqual(self.no_ar.views, 1)


class PaginasTests(TestCase):

    def setUp(self):
        self.cat = BlogCategory.objects.create(name="Volta às aulas", slug="volta-as-aulas")
        self.post = criar_post(slug="artigo", category=self.cat)

    def test_lista_e_artigo_abrem_sem_sessao(self):
        for url in ("/blog/", "/blog/artigo/", "/blog/categoria/volta-as-aulas/", "/blog/rss/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_artigo_tem_cta_com_origem_marcada(self):
        html = self.client.get("/blog/artigo/").content.decode()
        self.assertIn("/signup/?tier=basic", html)
        self.assertIn("utm_source=blog", html)
        # meio do texto, coluna lateral e fim do artigo
        self.assertIn("utm_medium=meio-do-artigo", html)
        self.assertIn("utm_medium=fim-do-artigo", html)
        self.assertIn("utm_medium=lateral", html)
        self.assertIn("utm_campaign=artigo", html)

    def test_artigo_traz_o_que_o_google_precisa(self):
        html = self.client.get("/blog/artigo/").content.decode()
        self.assertIn('rel="canonical"', html)
        self.assertIn('"@type":"BlogPosting"', html)
        self.assertIn('"@type":"BreadcrumbList"', html)
        self.assertIn('property="og:title"', html)
        self.assertNotIn("noindex", html)

    def test_categoria_filtra(self):
        outra = BlogCategory.objects.create(name="Dicas", slug="dicas")
        criar_post(title="De outra editoria", slug="outro", category=outra)
        html = self.client.get("/blog/categoria/volta-as-aulas/").content.decode()
        self.assertNotIn("De outra editoria", html)

    def test_busca_encontra_pelo_corpo(self):
        criar_post(title="Achável", slug="achavel", content="Fala sobre inadimplência.")
        html = self.client.get("/blog/", {"q": "inadimplência"}).content.decode()
        self.assertIn("Achável", html)
        self.assertNotIn("Como cobrar aula particular</a>", html)

    def test_categoria_inexistente_da_404(self):
        self.assertEqual(self.client.get("/blog/categoria/nao-existe/").status_code, 404)

    def test_robots_aponta_o_sitemap_e_fecha_a_area_do_cliente(self):
        texto = self.client.get("/robots.txt").content.decode()
        self.assertIn("Sitemap:", texto)
        self.assertIn("Disallow: /dashboard/", texto)
        self.assertIn("Allow: /blog/", texto)

    def test_landing_aponta_para_o_blog(self):
        html = self.client.get("/").content.decode()
        self.assertIn('href="/blog/"', html)


class ModeloTests(TestCase):

    def test_slug_sai_do_titulo_e_nao_repete(self):
        a = BlogPost.objects.create(title="Quanto cobrar", content="x")
        b = BlogPost.objects.create(title="Quanto cobrar", content="y")
        self.assertEqual(a.slug, "quanto-cobrar")
        self.assertEqual(b.slug, "quanto-cobrar-2")

    def test_publicar_sem_data_preenche_a_data(self):
        post = BlogPost.objects.create(
            title="Sem data", content="x", status=BlogPost.STATUS_PUBLISHED
        )
        self.assertIsNotNone(post.published_at)
        self.assertTrue(post.is_published)

    def test_minutos_de_leitura_calculados_ao_salvar(self):
        post = BlogPost.objects.create(title="Longo", content="palavra " * 600)
        self.assertEqual(post.reading_minutes, 3)

    def test_sumario_so_aparece_com_tres_secoes(self):
        curto = criar_post(slug="curto", content="## A\n\nx\n\n## B\n\ny")
        self.assertEqual(curto.sumario(), [])
        longo = criar_post(slug="longo", content="## A\n\nx\n\n## B\n\ny\n\n## C\n\nz")
        self.assertEqual(len(longo.sumario()), 3)

    def test_relacionados_preferem_a_mesma_editoria_e_nunca_o_proprio(self):
        cat = BlogCategory.objects.create(name="Dinheiro", slug="dinheiro")
        principal = criar_post(slug="principal", category=cat)
        criar_post(slug="mesma-editoria", category=cat)
        criar_post(slug="outra-editoria")
        relacionados = principal.relacionados()
        self.assertNotIn(principal, relacionados)
        self.assertEqual(relacionados[0].slug, "mesma-editoria")


class SeedTests(TestCase):

    def test_comando_cria_e_nao_duplica(self):
        from django.core.management import call_command
        from io import StringIO

        call_command("blog_seed", stdout=StringIO())
        primeiro = BlogPost.objects.count()
        self.assertGreater(primeiro, 0)
        self.assertGreater(BlogCategory.objects.count(), 0)

        call_command("blog_seed", stdout=StringIO())
        self.assertEqual(BlogPost.objects.count(), primeiro)

    def test_artigos_de_lancamento_nascem_como_rascunho(self):
        from django.core.management import call_command
        from io import StringIO

        call_command("blog_seed", stdout=StringIO())
        self.assertEqual(BlogPost.objects.published().count(), 0)

    def test_agendar_poe_dois_por_dia_na_fila(self):
        from django.core.management import call_command
        from io import StringIO

        call_command("blog_seed", "--agendar", "2", "--publicar-agora", "1", stdout=StringIO())
        self.assertEqual(BlogPost.objects.published().count(), 1)
        self.assertGreater(BlogPost.objects.scheduled().count(), 0)
        self.assertEqual(BlogPost.objects.filter(status=BlogPost.STATUS_DRAFT).count(), 0)
