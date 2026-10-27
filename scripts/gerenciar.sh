#!/bin/sh
# Roda um comando do manage.py no servidor como o usuário da aplicação ("app"),
# para que arquivos do banco criados pelo comando continuem graváveis por ela.
# Uso: fly ssh console -C "/app/scripts/gerenciar.sh criar_administrador --email ... --nome ..."
set -e
cd /app
exec su app -s /bin/sh -c 'exec python manage.py "$@"' -- manage "$@"
