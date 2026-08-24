FROM python:3.12-slim

WORKDIR /app

# Dependencias com versoes fixas (ver requirements.txt).
# Copiado antes do resto do codigo para aproveitar o cache de camada do Docker:
# alterar um template nao obriga a reinstalar tudo.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Mesmo backend de static que em produção (STORAGES["staticfiles"]); falhar o build se vazio.
RUN python manage.py collectstatic --noinput

EXPOSE 8000
# O blog nasce com os artigos de lancamento. `--se-vazio` faz a semeadura
# acontecer uma unica vez, na estreia: se ja existir qualquer artigo, o
# comando nao faz nada, e artigo apagado depois nao ressuscita no proximo
# deploy. O `|| true` e um segmento a parte de proposito: semear e acessorio
# e nao pode, em hipotese nenhuma, impedir o gunicorn de arrancar.
CMD python manage.py migrate --noinput && python manage.py create_master_user 2>/dev/null || true; python manage.py blog_seed --se-vazio --publicar-agora 2 --agendar 2 || true; exec gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
