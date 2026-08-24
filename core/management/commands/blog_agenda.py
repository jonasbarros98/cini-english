"""
Mostra e monta a fila de publicação do blog.

Sem argumentos, é só um relatório: o que está no ar, o que sai nos próximos
dias e quantos rascunhos ainda existem. Com --por-dia, pega os rascunhos e
distribui pelos próximos dias, uma ou duas postagens por dia.

Uso:
    .venv/Scripts/python.exe dev_local.py blog_agenda
    .venv/Scripts/python.exe dev_local.py blog_agenda --por-dia 2
    .venv/Scripts/python.exe dev_local.py blog_agenda --por-dia 1 --inicio 2026-09-01
    .venv/Scripts/python.exe dev_local.py blog_agenda --limpar

Não existe tarefa periódica por trás disto. Um artigo agendado entra no ar
porque a consulta do blog passa a incluí-lo quando o relógio passa da data.
"""

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from core.blog_schedule import agendar, formatar_br
from core.models import BlogPost


class Command(BaseCommand):
    help = "Mostra a fila de publicação do blog e agenda os rascunhos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--por-dia", type=int, default=0, metavar="N",
            help="Agenda os rascunhos, N por dia. Sem isto, só mostra a fila.",
        )
        parser.add_argument(
            "--inicio", type=str, default=None, metavar="AAAA-MM-DD",
            help="Primeiro dia da fila. Sem isto, começa amanhã.",
        )
        parser.add_argument(
            "--domingo", action="store_true",
            help="Usa domingo também. Por omissão a fila pula domingo.",
        )
        parser.add_argument(
            "--limpar", action="store_true",
            help="Tira da fila tudo que estava agendado e devolve a rascunho.",
        )

    def handle(self, *args, **op):
        if op["limpar"]:
            n = BlogPost.objects.scheduled().update(status=BlogPost.STATUS_DRAFT)
            self.stdout.write(self.style.WARNING(f"{n} artigo(s) saíram da fila e voltaram a rascunho."))

        if op["por_dia"]:
            rascunhos = list(
                BlogPost.objects.filter(status=BlogPost.STATUS_DRAFT).order_by("created_at", "id")
            )
            if not rascunhos:
                self.stdout.write(self.style.WARNING("Nenhum rascunho para agendar."))
            else:
                inicio = None
                if op["inicio"]:
                    try:
                        inicio = date.fromisoformat(op["inicio"])
                    except ValueError:
                        raise CommandError("--inicio precisa ser AAAA-MM-DD, por exemplo 2026-09-01.")
                plano = agendar(
                    rascunhos,
                    por_dia=op["por_dia"],
                    inicio=inicio,
                    pular_domingo=not op["domingo"],
                )
                self.stdout.write(
                    self.style.SUCCESS(f"{len(plano)} artigo(s) na fila, {op['por_dia']} por dia.\n")
                )

        self._relatorio()

    def _relatorio(self):
        no_ar = BlogPost.objects.published()
        fila = BlogPost.objects.scheduled()
        rascunhos = BlogPost.objects.filter(status=BlogPost.STATUS_DRAFT)

        self.stdout.write(self.style.SUCCESS(f"\nNo ar: {no_ar.count()}"))
        for post in no_ar[:5]:
            self.stdout.write(f"  {formatar_br(post.published_at)}  {post.title}")
        if no_ar.count() > 5:
            self.stdout.write(f"  ... e mais {no_ar.count() - 5}")

        self.stdout.write(self.style.SUCCESS(f"\nNa fila: {fila.count()}"))
        for post in fila:
            self.stdout.write(f"  {formatar_br(post.published_at)}  {post.title}")

        self.stdout.write(self.style.SUCCESS(f"\nRascunhos: {rascunhos.count()}"))
        for post in rascunhos[:10]:
            self.stdout.write(f"  {post.title}")

        if fila.count() == 0 and rascunhos.count() > 0:
            self.stdout.write(
                "\nA fila está vazia e existe rascunho parado. Para encher:\n"
                "  dev_local.py blog_agenda --por-dia 2"
            )
