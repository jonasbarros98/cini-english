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
CMD python manage.py migrate --noinput && python manage.py create_master_user 2>/dev/null || true && exec gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
