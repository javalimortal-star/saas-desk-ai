# SaaS Desk AI

Primeira fatia vertical de uma central de atendimento assistida por IA. Nesta entrega, um Solicitante pode registrar uma Solicitação pela interface pública ou pela API e recebe um Protocolo não sequencial.

## Executar localmente

Pré-requisito: Docker Desktop.

```bash
docker compose up --build
```

A interface fica disponível em `http://localhost:8000/`.

## Testes

Com o serviço `db` em execução:

```bash
docker compose up -d db
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
```

No Linux ou macOS, use `.venv/bin/python` no lugar de `.venv/Scripts/python`.

O PostgreSQL do Compose é publicado em `localhost:55432` para evitar conflito com instalações locais na porta padrão.
