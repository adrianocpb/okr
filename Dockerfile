# Imagem do servidor (Fly.io). Banco SQLite no disco permanente montado em /data.
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DJANGO_SETTINGS_MODULE=config.settings.prod

WORKDIR /app

COPY requirements/ requirements/
RUN pip install -r requirements/prod.txt

COPY . .

# Os arquivos estáticos são gerados na imagem. As variáveis abaixo existem só
# para este passo (as de verdade vêm do fly.toml e de `fly secrets`).
RUN DJANGO_SECRET_KEY="somente-para-gerar-arquivos-estaticos-na-construcao-da-imagem" \
    DJANGO_ALLOWED_HOSTS="localhost" \
    DATABASE_URL="sqlite:////tmp/construcao.sqlite3" \
    python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 app && chmod +x scripts/iniciar_servidor.sh scripts/gerenciar.sh

EXPOSE 8080
CMD ["scripts/iniciar_servidor.sh"]
