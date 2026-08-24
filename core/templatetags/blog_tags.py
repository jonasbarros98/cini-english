"""
Filtros de data do blog.

O projeto roda com LANGUAGE_CODE en-us e TIME_ZONE UTC, e mexer nisso agora
mudaria a hora que aparece na agenda de gente que já usa o sistema. O blog
resolve o problema dele sozinho: converte para Brasília e escreve o mês em
português, sem tocar em nada global.
"""

from django import template

from ..blog_schedule import TZ_BR

register = template.Library()

MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)


@register.filter
def data_extensa(dt):
    """24 de agosto de 2026"""
    if not dt:
        return ""
    local = dt.astimezone(TZ_BR)
    return f"{local.day} de {MESES[local.month - 1]} de {local.year}"


@register.filter
def data_curta(dt):
    """24/08/2026"""
    if not dt:
        return ""
    return f"{dt.astimezone(TZ_BR):%d/%m/%Y}"


@register.filter
def data_hora(dt):
    """24/08/2026 às 09:00"""
    if not dt:
        return ""
    local = dt.astimezone(TZ_BR)
    return f"{local:%d/%m/%Y} às {local:%H:%M}"


@register.filter
def iso(dt):
    """Formato que o <time datetime> e o schema.org esperam."""
    return dt.isoformat() if dt else ""
