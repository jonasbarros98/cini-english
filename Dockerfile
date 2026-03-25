FROM python:3.12-slim

WORKDIR /app

# Dependencias em UTF-8 (evita problema de encoding do requirements.txt no Windows)
RUN printf '%s\n' \
  'Django>=4.2' \
  'djangorestframework' \
  'django-cors-headers' \
  'dj-database-url' \
  'python-dotenv' \
  'whitenoise' \
  'stripe' \
  'Pillow' \
  'psycopg2-binary' \
  'gunicorn' \
  'django-anymail[resend]' \
  'google-auth>=2.29.0' \
  'django-storages[s3]' \
  'boto3' \
  > requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Migrate + collectstatic + gunicorn (compativel com preDeployCommand do Railway)
RUN python manage.py collectstatic --noinput 2>/dev/null || true

EXPOSE 8000
CMD python manage.py migrate --noinput && python manage.py create_master_user 2>/dev/null || true && exec gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
