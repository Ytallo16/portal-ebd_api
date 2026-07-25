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

## Importação de alunos

O endpoint `POST /api/v1/students/import/` recebe um CSV no campo multipart
`arquivo` e cria apenas uma prévia validada. Nenhum aluno é cadastrado nessa
etapa. As colunas obrigatórias são:

- `nome`
- `sexo` (`M`, `F`, `Masculino` ou `Feminino`)
- `data_nascimento` (`AAAA-MM-DD` ou `DD/MM/AAAA`)
- `turma` (nome da turma)

Também são aceitas as colunas opcionais `email`, `telefone`, `cep`, `rua`,
`numero`, `complemento`, `bairro`, `cidade`, `uf`, `responsavel_nome` e
`responsavel_telefone`.

A resposta informa o `lote_id`, colunas ausentes ou ignoradas e o resultado de
cada linha, incluindo os motivos das linhas inválidas. Para cadastrar as linhas
válidas, confirme em `POST /api/v1/students/import/{lote_id}/confirm/`.

O histórico está em `GET /api/v1/students/imports/`. Uma importação confirmada
pode ser desfeita por `POST /api/v1/students/import/{lote_id}/undo/`; nesse caso
os alunos do lote são inativados e suas frequências são preservadas. Alunos
alterados depois da importação não são desfeitos automaticamente. O limite é de
5 MB e 5.000 alunos por arquivo.
