#!/bin/sh
# Início do servidor no Fly.io: aplica as migrações no banco do disco permanente
# e sobe o gunicorn. O disco (/data) chega como root; a aplicação roda como "app".
set -e

mkdir -p /data
chown app:app /data

su app -s /bin/sh -c "python manage.py migrate --noinput"
exec su app -s /bin/sh -c "exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8080 \
  --workers 2 \
  --threads 4 \
  --timeout 60 \
  --access-logfile - \
  --forwarded-allow-ips '*'"
