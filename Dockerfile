FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DJANGO_DEBUG=0
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt "psycopg[binary]>=3.2" "redis>=5"
COPY . .
RUN useradd -m app && mkdir -p /app/media && chown -R app /app
USER app
RUN DJANGO_SECRET_KEY=build-only-build-only-build-only-0000 python manage.py collectstatic --noinput
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/healthz/')" || exit 1
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn studysync.wsgi -c gunicorn.conf.py"]
