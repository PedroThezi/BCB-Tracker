# BCB-Tracker

Pipeline de dados e dashboard para acompanhar as séries de **Dólar Comercial
(SGS 1)** e **Selic Meta Anualizada (SGS 432)** do Banco Central do Brasil
(BCB). Os dados são coletados da API pública do BCB, persistidos em
PostgreSQL (Neon) e visualizados em um dashboard Streamlit com gráficos
Plotly. Um workflow diário do GitHub Actions mantém a base atualizada.

## Funcionalidades

- Coleta diária das séries SGS do BCB (últimos 10 anos) com retentativas
  e backoff exponencial.
- Persistência idempotente no PostgreSQL via `ON CONFLICT (data, tipo) DO NOTHING`.
- View pivotada `cotacao_dolar_selic_pivot` com colunas `data`, `dolar`,
  `selic_meta` e suas variações percentuais diárias (calculadas via
  `LAG()`) para análises tabulares.
- Dashboard Streamlit com gráficos de Dólar (spline) e Selic (degrau),
  marcadores em todos os pontos, variação % no hover, métricas de último
  valor, tabela de estatísticas descritivas e dados brutos com variação.
- Três granularidades temporais: **Semana** (7 dias), **Mês** (30 dias) e
  **Acumulado** (média mensal histórica).
- Atualização automática diária via GitHub Actions (03:00 UTC).

## Séries coletadas

| Série | Código SGS | Tipo armazenado |
|---|---:|---|
| Dólar comercial | 1 | `dolar` |
| Selic Meta anualizada | 432 | `selic_meta` |

> A Selic Meta (SGS 432) é a taxa alvo anualizada definida pelo Copom,
> não a taxa Selic over diária.

## Banco de dados

### Tabela `cotacao_dolar_selic`

| Coluna | Tipo | Restrição |
|---|---|---|
| `id` | `SERIAL` | `PRIMARY KEY` |
| `data` | `DATE` | `NOT NULL` |
| `tipo` | `VARCHAR(20)` | `NOT NULL`, `CHECK IN ('dolar', 'selic_meta')` |
| `valor` | `DECIMAL(10,4)` | `NOT NULL` |
| `created_at` | `TIMESTAMP` | `DEFAULT NOW()` |

Constraint única: `(data, tipo)`.

### View `cotacao_dolar_selic_pivot`

| Coluna | Origem |
|---|---|
| `data` | `GROUP BY data` |
| `dolar` | `MAX(CASE WHEN tipo = 'dolar' THEN valor END)` |
| `selic_meta` | `MAX(CASE WHEN tipo = 'selic_meta' THEN valor END)` |
| `dolar_variacao` | variação % diária (LAG sobre `dolar`) |
| `selic_meta_variacao` | variação % diária (LAG sobre `selic_meta`) |

## Execução local

### Requisitos

- Python 3.11
- Docker e Docker Compose (opcional, para execução containerizada)
- Uma instância PostgreSQL (recomenda-se o Neon) — defina `DATABASE_URL`

### Configuração

Crie um arquivo `.env` na raiz com a connection string do Neon:

```env
DATABASE_URL=postgresql://usuario:senha@host/neondb?sslmode=require
```

> **Não versione o `.env`.** Ele está protegido pelo `.gitignore`.

### Com Docker

```bash
docker compose up -d --build
```

O serviço `streamlit-app` sobe na porta `8502` (mapeada para `8501` no
container) e exibe o dashboard em
[http://localhost:8502](http://localhost:8502).

> O ETL **não** roda dentro do container — ele é desacoplado e executado
> diariamente no GitHub Actions. Em ambiente local, rode-o manualmente:

```bash
docker compose exec -T streamlit-app python -c "from config.database import create_tables; create_tables()"
docker compose exec -T streamlit-app python -c "from scripts.etl import load_data; load_data()"
```

### Sem Docker

```bash
pip install -r requirements.txt

python -c "from config.database import create_tables; create_tables()"
python -c "from scripts.etl import load_data; load_data()"

streamlit run main.py
```

## Atualização automática

O workflow `.github/workflows/update_bcb_series.yml` executa a ingestão
diariamente às **03:00 UTC** e também pode ser disparado manualmente pela
aba **Actions** do repositório.

No GitHub, configure o secret **`NEON_DATABASE_URL`** (ou `DATABASE_URL`)
em **Settings > Secrets and variables > Actions**, no environment
`production`, usando a connection string completa do Neon.

## Estrutura do projeto

```
BCB-Tracker/
├── main.py                          # Entrypoint Streamlit: page config + main()
├── app/
│   ├── __init__.py                  # Marca `app/` como pacote Python
│   ├── data.py                      # Acesso a dados (fetch_data, build_long_df)
│   └── views.py                     # UI: tokens, formatters, charts, renderers, CSS
├── config/
│   └── database.py                  # Engine SQLAlchemy, criação de tabela e view
├── scripts/
│   ├── fetch_bcb_series.py          # Cliente da API SGS/BCB com retry
│   └── etl.py                       # Orquestra fetch → upsert no PostgreSQL
├── .github/workflows/
│   └── update_bcb_series.yml        # Job diário (03:00 UTC)
├── .streamlit/
│   └── config.toml                  # Tema light do Streamlit
├── docker-compose.yml               # Serviço streamlit-app
├── Dockerfile                       # Imagem Python 3.11 slim
├── requirements.txt                 # Dependências Python
└── .env                             # DATABASE_URL (ignorado pelo git)
```

## Variáveis de ambiente

| Variável | Finalidade | Obrigatória |
|---|---|---|
| `DATABASE_URL` | Connection string PostgreSQL (Neon) | Sim (local/prod) |
| `NEON_DATABASE_URL` | Nome alternativo, usado no GitHub Actions | Sim (CI) |

A aplicação **não** usa fallback para `localhost` — defina explicitamente
uma das duas variáveis.

## Adicionando uma nova série

1. Adicione a tupla `(código_sgs, tipo)` à lista `SERIES` em
   `scripts/etl.py`.
2. Atualize a constraint `CHECK` em `config/database.py::create_tables()`
   para incluir o novo `tipo`.
3. Ajuste a SQL da view pivot em `config/database.py` para expor a nova
   coluna e sua variação.
4. Em `app/data.py::build_long_df`, adicione o mapeamento no loop
   `series_map` para que a nova série apareça na tabela de dados brutos
   e nas estatísticas.
5. Em `app/views.py`, ajuste `_build_chart` e os wrappers
   `build_chart_dolar` / `build_chart_selic` para tratar a nova série
   (cor, formato do hover, forma da linha).

## Verificação manual

Como o projeto não possui suíte de testes automatizados, valide
manualmente após mudanças:

1. Rode o ETL e confirme que a tabela `cotacao_dolar_selic` contém
   registros recentes (`SELECT MAX(data) FROM cotacao_dolar_selic;`).
2. Inicie o Streamlit e verifique se os gráficos renderizam e as
   métricas mostram os últimos valores.
3. Consulte a view `cotacao_dolar_selic_pivot` e confira se as colunas
   `dolar` e `selic_meta` estão preenchidas para as datas esperadas.

## Segurança

- **Nunca** versione `.env` nem connection strings.
- Use **secrets** do GitHub Actions (não variables) para credenciais
  automatizadas.
- O `.env` está protegido pelo `.gitignore`.
