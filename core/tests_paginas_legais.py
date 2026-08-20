"""Testes das paginas legais.

Elas existem por dois motivos, e os dois exigem que abram SEM sessao: a Meta
precisa de as ler para publicar a app do WhatsApp, e um pai que quer saber o
que o sistema faz com os dados do filho nao devia ter de criar conta para isso.

Por isso o teste mais importante aqui e o mais simples: anonimo, 200.
"""
from django.test import TestCase
from django.urls import reverse

CNPJ = "44.318.881/0001-69"
RAZAO_SOCIAL = "JB Sistemas e Serviços de Informática LTDA"
CONTATO = "Educaflowone@gmail.com"

PAGINAS = ["privacidade", "termos", "exclusao-de-dados"]


class PaginasLegaisTests(TestCase):

    def test_abrem_sem_sessao(self):
        for nome in PAGINAS:
            with self.subTest(pagina=nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 200)

    def test_identificam_a_empresa_e_o_contato(self):
        """Documento legal sem quem responde por ele nao serve para nada."""
        for nome in PAGINAS:
            with self.subTest(pagina=nome):
                html = self.client.get(reverse(nome)).content.decode()
                self.assertIn(CNPJ, html)
                self.assertIn(RAZAO_SOCIAL, html)
                self.assertIn(CONTATO, html)

    def test_sem_tag_django_por_resolver(self):
        for nome in PAGINAS:
            with self.subTest(pagina=nome):
                html = self.client.get(reverse(nome)).content.decode()
                self.assertNotIn("{%", html)
                self.assertNotIn("{{", html)

    def test_uma_leva_a_outra(self):
        """Quem chega pela politica tem de conseguir chegar a exclusao, e vice-versa."""
        privacidade = self.client.get(reverse("privacidade")).content.decode()
        self.assertIn(reverse("exclusao-de-dados"), privacidade)
        self.assertIn(reverse("termos"), privacidade)

        exclusao = self.client.get(reverse("exclusao-de-dados")).content.decode()
        self.assertIn(reverse("privacidade"), exclusao)

    def test_privacidade_nomeia_os_terceiros_que_recebem_dados(self):
        """Se um fornecedor sair ou entrar no sistema, este teste obriga a mexer aqui."""
        html = self.client.get(reverse("privacidade")).content.decode()
        for terceiro in ("Railway", "Cloudflare R2", "Stripe", "Resend", "Meta", "Google"):
            with self.subTest(terceiro=terceiro):
                self.assertIn(terceiro, html)

    def test_privacidade_trata_de_menores(self):
        """A maioria dos alunos e menor de idade: omitir isso seria o pior erro."""
        html = self.client.get(reverse("privacidade")).content.decode()
        self.assertIn("adolescentes", html)
        self.assertIn("art. 14", html)

    def test_exclusao_diz_prazo(self):
        html = self.client.get(reverse("exclusao-de-dados")).content.decode()
        self.assertIn("30 dias", html)

    def test_paginas_nao_carregam_o_pixel_da_meta(self):
        """Rastrear quem foi ler a politica de privacidade seria de mau gosto."""
        for nome in PAGINAS:
            with self.subTest(pagina=nome):
                html = self.client.get(reverse(nome)).content.decode()
                self.assertNotIn("fbevents.js", html)
