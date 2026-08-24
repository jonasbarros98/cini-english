"""
Blog: categorias e artigos.

Escrita à mão, e não pelo `makemigrations`, de propósito: no momento em que o
blog foi construído havia outra alteração de modelo em curso na mesma árvore
(um campo novo em PixCharge). Gerar automaticamente teria arrastado essa
alteração pela metade para dentro desta migração. Aqui só entra o blog.

Depende da `0058`, e não da `0059`, também de propósito: a `0059` é da frente do
Pix e ainda não entrou na `main`. Amarrar o blog a ela impediria o blog de subir
sozinho. O blog não precisa de nada do Pix.

> QUANDO A FRENTE DO PIX FOR FUNDIDA
> O grafo fica com duas folhas, `0059` e `0061`, porque cada frente saiu da
> `0058`. É o mesmo caso das duas `0057`, resolvido em `170d98a`: rode
> `makemigrations --merge` e commite a migração de junção, ou acrescente
> `('core', '0059_...')` às dependências da `0061`, que é o que ela de facto
> precisa (altera uma tabela que a `0059` cria).
"""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0058_merge_20260822_1025"),
    ]

    operations = [
        migrations.CreateModel(
            name="BlogCategory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=60, unique=True, verbose_name="Nome")),
                ("slug", models.SlugField(max_length=80, unique=True)),
                ("description", models.CharField(blank=True, help_text="Uma linha, aparece no topo da página da categoria.", max_length=220)),
                ("order", models.PositiveSmallIntegerField(default=0, help_text="Menor número aparece primeiro no menu do blog.")),
            ],
            options={
                "verbose_name": "Categoria do blog",
                "verbose_name_plural": "Categorias do blog",
                "ordering": ["order", "name"],
            },
        ),
        migrations.CreateModel(
            name="BlogPost",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(help_text="O que o Google mostra. Até 60 caracteres aparece inteiro na busca.", max_length=160, verbose_name="Título")),
                ("slug", models.SlugField(blank=True, help_text="Endereço do artigo. Deixe vazio para gerar do título. Depois de publicado, mudar aqui quebra os links que já circulam.", max_length=180, unique=True)),
                ("dek", models.CharField(blank=True, help_text="A frase abaixo do título, no cartão da lista e nas redes.", max_length=300, verbose_name="Linha de apoio")),
                ("content", models.TextField(help_text="Markdown. ## título de seção, ### subtítulo, - lista, > destaque, **negrito**, [texto](link), | tabela |. Escreva [[cta]] numa linha sozinha para escolher onde entra o convite de cadastro; sem isso ele entra sozinho no meio.", verbose_name="Texto do artigo")),
                ("cover", models.ImageField(blank=True, help_text="Proporção 16:9, pelo menos 1200x630 para aparecer bem no WhatsApp.", null=True, upload_to="blog/capas/%Y/%m/", verbose_name="Imagem de capa")),
                ("cover_alt", models.CharField(blank=True, help_text="O que a imagem mostra, para quem usa leitor de tela.", max_length=180, verbose_name="Descrição da capa")),
                ("author_name", models.CharField(default="Equipe EDUCAflowOne", max_length=90, verbose_name="Autor")),
                ("author_role", models.CharField(blank=True, max_length=120, verbose_name="Cargo do autor")),
                ("status", models.CharField(choices=[("draft", "Rascunho"), ("published", "Publicado")], db_index=True, default="draft", max_length=12)),
                ("featured", models.BooleanField(default=False, help_text="O mais recente marcado assim abre a página do blog.", verbose_name="Destaque")),
                ("published_at", models.DateTimeField(blank=True, db_index=True, help_text="Preenchido sozinho ao publicar. Data futura agenda o artigo.", null=True, verbose_name="Publicado em")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("seo_title", models.CharField(blank=True, help_text="Vazio usa o título do artigo.", max_length=70, verbose_name="Título no Google")),
                ("seo_description", models.CharField(blank=True, help_text="Vazio usa a linha de apoio, ou o primeiro parágrafo.", max_length=180, verbose_name="Descrição no Google")),
                ("keywords", models.CharField(blank=True, help_text="Separadas por vírgula. Uso interno, para você lembrar do alvo.", max_length=240, verbose_name="Palavras-chave")),
                ("cta_title", models.CharField(blank=True, max_length=120, verbose_name="Título do convite")),
                ("cta_text", models.CharField(blank=True, max_length=300, verbose_name="Texto do convite")),
                ("cta_button", models.CharField(blank=True, max_length=60, verbose_name="Botão do convite")),
                ("views", models.PositiveIntegerField(default=0, verbose_name="Leituras")),
                ("reading_minutes", models.PositiveSmallIntegerField(default=1, verbose_name="Minutos de leitura")),
                ("category", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="posts", to="core.blogcategory", verbose_name="Categoria")),
            ],
            options={
                "verbose_name": "Artigo do blog",
                "verbose_name_plural": "Artigos do blog",
                "ordering": ["-published_at", "-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="blogpost",
            index=models.Index(fields=["status", "-published_at"], name="blog_status_data_idx"),
        ),
    ]
