"""
Renderizador de Markdown do blog.

Por que escrever em vez de instalar uma biblioteca: o `requirements.txt` deste
projeto e propositalmente fixado, e cada dependencia nova entra no build do
Docker que serve clientes pagantes. O texto de um artigo usa um punhado de
marcas (titulo, lista, negrito, link, citacao, tabela, imagem) e nenhuma delas
justifica uma dependencia a mais na imagem de producao.

O que ele aceita, e nada alem disso:

    ## Titulo de secao          -> <h2 id="slug">
    ### Subtitulo               -> <h3 id="slug">
    - item / * item             -> <ul>
    1. item                     -> <ol>
    > texto                     -> <blockquote> (caixa de destaque)
    | a | b |                   -> <table> (a segunda linha e o separador)
    tres crases                 -> <pre><code>
    ---                         -> <hr>
    ![alt](url)                 -> <figure><img>
    [[cta]]                     -> ponto de insercao do bloco de conversao
    **negrito**  *italico*  crase-codigo-crase  [texto](url)

Regra de seguranca: todo o texto e escapado ANTES de virar HTML. O autor e
administrador e teoricamente confiavel, mas um artigo colado de outro lugar nao
deveria conseguir injetar <script> numa pagina publica.
"""

import re
import unicodedata

# Marca que o autor escreve no corpo para escolher onde entra o bloco de CTA.
CTA_MARKER = "[[cta]]"
# Sentinela devolvida no HTML; o template troca por markup real.
CTA_TOKEN = "<!--EDUCAFLOW_CTA-->"

_ESCAPES = (
    ("&", "&amp;"),
    ("<", "&lt;"),
    (">", "&gt;"),
    ('"', "&quot;"),
)

_RE_IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+&quot;([^&]*)&quot;)?\)")
_RE_LINK = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
_RE_BOLD = re.compile(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", re.S)
_RE_ITALIC = re.compile(r"(?<![\*\w])\*(?=\S)([^\*]+?)(?<=\S)\*(?![\*\w])", re.S)
_RE_CODE = re.compile(r"`([^`]+)`")
_RE_UL = re.compile(r"^[-*]\s+(.*)$")
_RE_OL = re.compile(r"^\d+[.)]\s+(.*)$")
_RE_TABLE_SEP = re.compile(r"^\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?$")
_RE_TAG = re.compile(r"<[^>]+>")


def slugify_heading(text, taken=None):
    """Ancora estavel para o indice do artigo. Sem acento, sem simbolo."""
    plain = _RE_TAG.sub("", text)
    plain = unicodedata.normalize("NFKD", plain).encode("ascii", "ignore").decode()
    plain = re.sub(r"[^\w\s-]", "", plain).strip().lower()
    slug = re.sub(r"[\s_-]+", "-", plain).strip("-") or "secao"
    if taken is None:
        return slug
    base, n = slug, 2
    while slug in taken:
        slug = base + "-" + str(n)
        n += 1
    taken.add(slug)
    return slug


def _escape(text):
    for old, new in _ESCAPES:
        text = text.replace(old, new)
    return text


def _external(url):
    return url.startswith("http") and "educaflowone" not in url


def _inline(text):
    """Aplica as marcas de linha sobre texto JA escapado."""
    text = _RE_IMAGE.sub(
        lambda m: '<img src="%s" alt="%s" loading="lazy">' % (m.group(2), m.group(1)),
        text,
    )
    text = _RE_CODE.sub(r"<code>\1</code>", text)
    text = _RE_BOLD.sub(r"<strong>\1</strong>", text)
    text = _RE_ITALIC.sub(r"<em>\1</em>", text)

    def _link(m):
        label, url = m.group(1), m.group(2)
        rel = ' target="_blank" rel="noopener noreferrer"' if _external(url) else ""
        return '<a href="%s"%s>%s</a>' % (url, rel, label)

    return _RE_LINK.sub(_link, text)


def _flush(buf, out, tag):
    if not buf:
        return
    items = "".join("<li>" + item + "</li>" for item in buf)
    out.append("<" + tag + ">" + items + "</" + tag + ">")
    buf.clear()


def render(markdown_text):
    """
    Devolve (html, indice). O indice e uma lista de dicts {id, texto} com os
    <h2>, usada pelo sumario "Neste artigo" do template do artigo.
    """
    if not markdown_text:
        return "", []

    lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out, toc, taken = [], [], set()
    para, ul, ol, quote, table = [], [], [], [], []
    code = []
    in_code, code_lang = False, ""

    def close_para():
        if para:
            out.append("<p>" + " ".join(para) + "</p>")
            para.clear()

    def close_quote():
        if quote:
            out.append("<blockquote>" + " ".join(quote) + "</blockquote>")
            quote.clear()

    def close_table():
        if not table:
            return
        head, body = table[0], table[1:]
        cells = "".join("<th>" + c + "</th>" for c in head)
        rows = "".join(
            "<tr>" + "".join("<td>" + c + "</td>" for c in row) + "</tr>"
            for row in body
        )
        out.append(
            '<div class="tabela-rolavel"><table><thead><tr>'
            + cells
            + "</tr></thead><tbody>"
            + rows
            + "</tbody></table></div>"
        )
        table.clear()

    def close_all():
        close_para()
        _flush(ul, out, "ul")
        _flush(ol, out, "ol")
        close_quote()
        close_table()

    for raw in lines:
        stripped = raw.strip()

        # Bloco de codigo: passa cru (ja escapado), sem interpretar nada dentro.
        if stripped.startswith("```"):
            if in_code:
                lang = ' class="lang-' + code_lang + '"' if code_lang else ""
                out.append(
                    "<pre><code" + lang + ">" + "\n".join(code) + "</code></pre>"
                )
                code = []
                in_code, code_lang = False, ""
            else:
                close_all()
                in_code, code_lang = True, stripped[3:].strip()
            continue
        if in_code:
            code.append(_escape(raw.rstrip()))
            continue

        if not stripped:
            close_all()
            continue

        if stripped == CTA_MARKER:
            close_all()
            out.append(CTA_TOKEN)
            continue

        if stripped in ("---", "***", "___"):
            close_all()
            out.append("<hr>")
            continue

        if stripped.startswith("### "):
            close_all()
            cru = stripped[4:].strip()
            text = _inline(_escape(cru))
            out.append('<h3 id="' + slugify_heading(cru, taken) + '">' + text + "</h3>")
            continue

        if stripped.startswith("## "):
            close_all()
            cru = stripped[3:].strip()
            text = _inline(_escape(cru))
            anchor = slugify_heading(cru, taken)
            # O sumario recebe texto puro: quem escapa e o template.
            toc.append({"id": anchor, "texto": re.sub(r"[*`]", "", cru)})
            out.append('<h2 id="' + anchor + '">' + text + "</h2>")
            continue

        if stripped.startswith("> "):
            close_para()
            _flush(ul, out, "ul")
            _flush(ol, out, "ol")
            close_table()
            quote.append(_inline(_escape(stripped[2:].strip())))
            continue

        # Imagem sozinha na linha vira figura, com legenda opcional entre aspas.
        if stripped.startswith("!["):
            m = _RE_IMAGE.match(_escape(stripped))
            if m:
                close_all()
                caption = (
                    "<figcaption>" + m.group(3) + "</figcaption>" if m.group(3) else ""
                )
                out.append(
                    '<figure><img src="%s" alt="%s" loading="lazy">%s</figure>'
                    % (m.group(2), m.group(1), caption)
                )
                continue

        if stripped.startswith("|") and stripped.endswith("|"):
            close_para()
            _flush(ul, out, "ul")
            _flush(ol, out, "ol")
            close_quote()
            if _RE_TABLE_SEP.match(stripped):
                continue  # linha separadora do cabecalho
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            table.append([_inline(_escape(c)) for c in cells])
            continue

        m = _RE_UL.match(stripped)
        if m:
            close_para()
            _flush(ol, out, "ol")
            close_quote()
            close_table()
            ul.append(_inline(_escape(m.group(1))))
            continue

        m = _RE_OL.match(stripped)
        if m:
            close_para()
            _flush(ul, out, "ul")
            close_quote()
            close_table()
            ol.append(_inline(_escape(m.group(1))))
            continue

        _flush(ul, out, "ul")
        _flush(ol, out, "ol")
        close_quote()
        close_table()
        para.append(_inline(_escape(stripped)))

    if in_code and code:
        out.append("<pre><code>" + "\n".join(code) + "</code></pre>")
    close_all()

    return "".join(out), toc


def auto_cta(html, depois_do_titulo=2):
    """
    Se o autor nao marcou [[cta]], o bloco entra sozinho antes do N-esimo <h2>.

    O meio do artigo e onde o leitor ja entendeu que o problema e real e ainda
    nao terminou de ler: e o lugar que converte. Um artigo curto demais para ter
    esse titulo fica so com o CTA do fim, que o template sempre imprime.
    """
    if not html or CTA_TOKEN in html:
        return html
    pos, encontrados = 0, 0
    while True:
        idx = html.find("<h2", pos)
        if idx == -1:
            return html
        encontrados += 1
        if encontrados == depois_do_titulo:
            return html[:idx] + CTA_TOKEN + html[idx:]
        pos = idx + 3


def reading_minutes(markdown_text):
    """Minutos de leitura a 200 palavras por minuto, minimo de 1."""
    palavras = len(re.findall(r"\w+", markdown_text or ""))
    return max(1, round(palavras / 200))


def plain_excerpt(markdown_text, limite=180):
    """Primeiro paragrafo sem marcacao, para meta description e cartao da lista."""
    for bloco in (markdown_text or "").split("\n\n"):
        b = bloco.strip()
        if not b or b.startswith(("#", ">", "-", "*", "|", "```", "![", "[[")):
            continue
        texto = _RE_LINK.sub(r"\1", b)
        texto = re.sub(r"[*`]", "", texto).replace("\n", " ")
        texto = re.sub(r"\s+", " ", texto).strip()
        if len(texto) <= limite:
            return texto
        return texto[:limite].rsplit(" ", 1)[0] + "..."
    return ""
