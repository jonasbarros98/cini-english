"""
Cria as editorias e os artigos de lançamento do blog.

É idempotente por slug: rodar duas vezes não duplica nada e não sobrescreve
texto que já foi editado no /admin/. Depois de criado, quem manda no artigo é
o banco, não este ficheiro.

Uso:
    .venv/Scripts/python.exe dev_local.py blog_seed
    .venv/Scripts/python.exe dev_local.py blog_seed --agendar 2
    .venv/Scripts/python.exe dev_local.py blog_seed --agendar 1 --inicio 2026-08-25
    .venv/Scripts/python.exe dev_local.py blog_seed --publicar-agora 2
"""

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from core.blog_schedule import agendar, formatar_br
from core.blog_seed_content import ARTIGOS, CATEGORIAS
from core.models import BlogCategory, BlogPost


class Command(BaseCommand):
    help = "Cria as categorias e os artigos de lançamento do blog (sem duplicar)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--agendar", type=int, default=0, metavar="N",
            help="Põe os artigos criados na fila, N por dia, a partir de amanhã.",
        )
        parser.add_argument(
            "--inicio", type=str, default=None, metavar="AAAA-MM-DD",
            help="Primeiro dia da fila. Sem isto, começa amanhã.",
        )
        parser.add_argument(
            "--publicar-agora", type=int, default=0, metavar="N",
            help="Publica já os N primeiros, para o blog não nascer vazio.",
        )
        parser.add_argument(
            "--domingo", action="store_true",
            help="Usa domingo também. Por omissão a fila pula domingo.",
        )
        parser.add_argument(
            "--se-vazio", action="store_true",
            help="Não faz nada se já existir qualquer artigo. É assim que o "
                 "comando roda no preDeploy do Railway: semeia uma vez, na "
                 "estreia, e nunca ressuscita artigo que foi apagado depois.",
        )

    def handle(self, *args, **op):
        if op["se_vazio"] and BlogPost.objects.exists():
            self.stdout.write("Blog já tem artigo. Nada a semear.")
            return

        criadas = 0
        for dados in CATEGORIAS:
            _, nova = BlogCategory.objects.get_or_create(
                slug=dados["slug"],
                defaults={
                    "name": dados["name"],
                    "description": dados["description"],
                    "order": dados["order"],
                },
            )
            criadas += 1 if nova else 0
        self.stdout.write(f"Categorias: {criadas} criada(s), {len(CATEGORIAS) - criadas} já existiam.")

        categorias = {c.slug: c for c in BlogCategory.objects.all()}
        novos, existentes = [], 0

        for artigo in ARTIGOS:
            if BlogPost.objects.filter(slug=artigo["slug"]).exists():
                existentes += 1
                continue
            post = BlogPost.objects.create(
                slug=artigo["slug"],
                title=artigo["title"],
                dek=artigo["dek"],
                content=artigo["content"].strip(),
                category=categorias.get(artigo["categoria"]),
                seo_title=artigo.get("seo_title", ""),
                seo_description=artigo.get("seo_description", ""),
                keywords=artigo.get("keywords", ""),
                cta_title=artigo.get("cta_title", ""),
                cta_text=artigo.get("cta_text", ""),
                cta_button=artigo.get("cta_button", ""),
                status=BlogPost.STATUS_DRAFT,
            )
            novos.append(post)

        self.stdout.write(
            f"Artigos: {len(novos)} criado(s) como rascunho, {existentes} já existiam."
        )

        if not novos:
            self.stdout.write(self.style.WARNING("Nada novo para agendar."))
            return

        publicar = min(op["publicar_agora"], len(novos))
        for post in novos[:publicar]:
            post.status = BlogPost.STATUS_PUBLISHED
            post.published_at = timezone.now()
            post.save()
            self.stdout.write(self.style.SUCCESS(f"  no ar agora: {post.title}"))
        if publicar:
            novos[0].featured = True
            novos[0].save(update_fields=["featured"])

        restantes = novos[publicar:]
        if op["agendar"] and restantes:
            inicio = None
            if op["inicio"]:
                try:
                    inicio = date.fromisoformat(op["inicio"])
                except ValueError:
                    raise CommandError("--inicio precisa ser AAAA-MM-DD, por exemplo 2026-08-25.")
            plano = agendar(
                restantes,
                por_dia=op["agendar"],
                inicio=inicio,
                pular_domingo=not op["domingo"],
            )
            self.stdout.write(self.style.SUCCESS(f"\nFila, {op['agendar']} por dia:"))
            for post, quando in plano:
                self.stdout.write(f"  {formatar_br(quando)}  {post.title}")
            self.stdout.write(
                "\nNinguém precisa clicar em nada na hora: cada artigo aparece no "
                "blog sozinho quando a data chegar."
            )
        elif restantes:
            self.stdout.write(
                f"{len(restantes)} artigo(s) ficaram em rascunho. Para pôr na fila:\n"
                "  dev_local.py blog_agenda --por-dia 2"
            )
