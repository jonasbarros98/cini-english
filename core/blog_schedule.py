"""
Fila de publicação do blog.

O plano é uma ou duas postagens por dia, escritas em lote e soltas aos poucos.
Isto aqui é o que transforma um monte de rascunhos numa fila com data e hora.

Como funciona, e por que não existe cron nenhum: um artigo com status
"publicado" e `published_at` no futuro simplesmente não passa pelo filtro de
`BlogPost.objects.published()`. Quando o relógio passa da data, passa a passar.
Nada precisa acordar de madrugada para publicar, e nada pode falhar de
madrugada e deixar o dia sem artigo.

O settings do projeto roda em UTC. Os horários daqui são de Brasília, porque é
o que o Jonas quer dizer quando diz "sai às nove da manhã", e a conversão é
feita neste ficheiro, num sítio só.
"""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

TZ_BR = ZoneInfo("America/Sao_Paulo")

# Manhã antes da primeira aula, e fim de tarde entre um aluno e outro: são as
# duas janelas em que professor particular pega no telemóvel.
HORARIOS_PADRAO = (time(9, 0), time(17, 30))

# Domingo é o pior dia para conteúdo de trabalho, e não vale queimar artigo nele.
DIAS_UTEIS_MAIS_SABADO = (0, 1, 2, 3, 4, 5)


def horarios_do_dia(por_dia: int) -> list:
    """Uma postagem sai de manhã. Duas, manhã e fim de tarde."""
    if por_dia <= 1:
        return [HORARIOS_PADRAO[0]]
    if por_dia == 2:
        return list(HORARIOS_PADRAO)
    # Acima de duas, reparte o dia entre 9h e 19h em partes iguais.
    passo = (19 - 9) / (por_dia - 1)
    return [time(int(9 + passo * i), 0) for i in range(por_dia)]


def gerar_datas(quantidade: int, por_dia: int = 1, inicio=None, pular_domingo: bool = True) -> list:
    """
    Devolve `quantidade` datas em UTC, `por_dia` por dia, a partir de `inicio`.

    `inicio` é uma data (não datetime) no fuso de Brasília. Sem ela, começa
    amanhã: agendar para hoje de manhã quando já é de tarde publicaria na hora,
    o que quase nunca é o que se quer ao montar uma fila.
    """
    if inicio is None:
        inicio = (timezone.now().astimezone(TZ_BR) + timedelta(days=1)).date()

    horas = horarios_do_dia(por_dia)
    datas, dia = [], inicio

    while len(datas) < quantidade:
        if pular_domingo and dia.weekday() == 6:
            dia += timedelta(days=1)
            continue
        for h in horas:
            if len(datas) >= quantidade:
                break
            local = datetime.combine(dia, h, tzinfo=TZ_BR)
            datas.append(local.astimezone(ZoneInfo("UTC")))
        dia += timedelta(days=1)

    return datas


def agendar(posts, por_dia: int = 1, inicio=None, pular_domingo: bool = True) -> list:
    """
    Põe a lista de artigos na fila, na ordem em que veio, e grava.

    Devolve a lista de (artigo, data) para quem chamou poder mostrar o plano.
    """
    from .models import BlogPost

    posts = list(posts)
    datas = gerar_datas(len(posts), por_dia, inicio, pular_domingo)

    plano = []
    for post, quando in zip(posts, datas):
        post.status = BlogPost.STATUS_PUBLISHED
        post.published_at = quando
        post.save(update_fields=["status", "published_at", "updated_at", "reading_minutes"])
        plano.append((post, quando))
    return plano


def formatar_br(dt) -> str:
    """Data e hora de Brasília, em português, sem depender do locale do Django."""
    if not dt:
        return "sem data"
    meses = (
        "janeiro", "fevereiro", "março", "abril", "maio", "junho",
        "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
    )
    local = dt.astimezone(TZ_BR)
    return f"{local.day} de {meses[local.month - 1]} de {local.year}, {local:%H:%M}"
