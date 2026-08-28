# BCB-Tracker

Dashboard em Streamlit para acompanhar as séries de dólar e Selic Meta do
Banco Central do Brasil (BCB), armazenadas em PostgreSQL/Neon.

## Funcionalidades

- Coleta dados da API SGS/BCB.
- Persiste os dados com idempotência no PostgreSQL.
- Disponibiliza dashboard em Streamlit.
- Mantém uma view pivotada para análises tabulares.
- Atualiza os dados diariamente usando GitHub Actions.

## Séries coletadas

| Série | Código SGS | Tipo armazenado |
|---|---:|---|
| Dólar comercial | 1 | `dolar` |
| Selic Meta anualizada | 432 | `selic_meta` |

## Banco de dados

Os dados ficam na tabela `cotacao_dolar_selic`, com as colunas `data`, `tipo` e
`valor`. A view `cotacao_dolar_selic_pivot` apresenta o formato:

| data | dolar | selic_meta |
|---|---:|---:|

## Execução local

Requisitos: Docker e Docker Compose.

Configure o arquivo `.env` com a connection string do Neon:

```env
DATABASE_URL=postgresql://usuario:senha@host/neondb?sslmode=require
```

Inicie os serviços:

```bash
docker compose up -d --build
```

O dashboard estará disponível em [http://localhost:8502](http://localhost:8502).
O PostgreSQL local é exposto em `localhost:5433`; a aplicação usa
`DATABASE_URL` quando essa variável está configurada.

Para executar a ingestão manualmente:

```bash
docker compose exec -T streamlit-app python -c "from config.database import create_tables; create_tables()"
docker compose exec -T streamlit-app python -c "from scripts.etl import load_data; load_data()"
```

## Atualização automática

O workflow
`.github/workflows/update_bcb_series.yml` executa a ingestão diariamente às
03:00 UTC e também pode ser iniciado manualmente pela aba **Actions**.

No repositório GitHub, crie o secret `NEON_DATABASE_URL` em **Settings > Secrets
and variables > Actions** usando a connection string do Neon.

## Estrutura

- `app/`: dashboard Streamlit.
- `config/database.py`: conexão e criação da tabela.
- `scripts/fetch_bcb_series.py`: cliente da API do BCB.
- `scripts/etl.py`: ingestão no PostgreSQL.
- `.github/workflows/update_bcb_series.yml`: automação diária.
- `docker-compose.yml`: execução local.

## Segurança

- Não versione `.env` nem connection strings.
- Use secrets do GitHub Actions para ambientes automatizados.
- O arquivo `.env` está protegido pelo `.gitignore`.