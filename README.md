# portal-ebd_api

Backend dockerizado com Django REST, JWT e PostgreSQL.

## Subir ambiente

Dentro de `portal-ebd_api`:

```bash
docker compose up --build
```

## URLs principais

- API base: `http://localhost:8000/api/v1/`
- Healthcheck: `GET /api/v1/health/`
- Login JWT: `POST /api/v1/auth/login`
- Refresh JWT: `POST /api/v1/auth/refresh`
- Logout: `POST /api/v1/auth/logout`
- Docs (Swagger): `GET /api/v1/docs/`
