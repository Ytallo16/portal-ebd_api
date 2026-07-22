#!/usr/bin/env sh
set -e

# Migrations (já commitadas no repositório)
python manage.py migrate --noinput

# Arquivos estáticos servidos pelo Nginx a partir de /app/staticfiles
python manage.py collectstatic --noinput

# Cria o superusuário a partir das variáveis de ambiente, se ainda não existir
if [ "$DJANGO_SUPERUSER_EMAIL" ] && [ "$DJANGO_SUPERUSER_PASSWORD" ]; then
  python manage.py shell << PYEOF
from accounts.models import User
email = "${DJANGO_SUPERUSER_EMAIL}"
password = "${DJANGO_SUPERUSER_PASSWORD}"
if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(email=email, password=password, nome="Admin")
    print("Superusuario criado:", email)
else:
    print("Superusuario ja existe:", email)
PYEOF
fi

exec gunicorn config.wsgi:application \
  --bind 0.0.0.0:8000 \
  --workers 3 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile -
