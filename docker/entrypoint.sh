#!/usr/bin/env sh
set -e

python manage.py makemigrations --noinput
python manage.py migrate --noinput
python manage.py seed_data || true

if [ "$DJANGO_SUPERUSER_EMAIL" ] && [ "$DJANGO_SUPERUSER_PASSWORD" ]; then
  python manage.py shell << PYEOF
from accounts.models import User
email = "${DJANGO_SUPERUSER_EMAIL}"
password = "${DJANGO_SUPERUSER_PASSWORD}"
if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(email=email, password=password, nome="Admin")
    print("Superusuário criado:", email)
else:
    print("Superusuário já existe:", email)
PYEOF
fi

python manage.py runserver 0.0.0.0:8000
