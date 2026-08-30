# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

BCB-Tracker is a data pipeline and dashboard for tracking Brazilian Central Bank (BCB) series: **Dólar Comercial (SGS 1)** and **Selic Meta Anualizada (SGS 432)**. Data is fetched from the public BCB API, stored in PostgreSQL (Neon), and visualized via a Streamlit dashboard. A daily GitHub Actions workflow keeps the data up to date.

The project has recently migrated from a Streamlit-only deployment to include **Metabase** for BI dashboards (see `docker-compose.yml`).

## Architecture

```
BCB-Tracker/
├── app/
│   └── app.py                 # Streamlit dashboard ( Plotly charts, metrics, stats table)
├── config/
│   └── database.py            # SQLAlchemy engine, connection, table/view creation
├── scripts/
│   ├── fetch_bcb_series.py    # BCB API client with retry logic
│   └── etl.py                 # Orchestrates fetch → upsert into PostgreSQL
├── .github/workflows/
│   └── update_bcb_series.yml  # Daily 03:00 UTC scheduled run
├── docker-compose.yml         # Metabase service (port 3000)
├── Dockerfile                 # Python 3.11 slim for ETL scripts
├── requirements.txt           # Python dependencies
└── .env                       # DATABASE_URL (not committed)
```

### Data Flow

1. **Fetch**: `scripts/fetch_bcb_series.py` → calls BCB API (`https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados`) for last 10 years
2. **Transform**: Normalizes dates (`%d/%m/%Y`), coerces numeric values, adds `tipo` column (`dolar` / `selic_meta`)
3. **Load**: `scripts/etl.py` → upserts into `cotacao_dolar_selic` table using `ON CONFLICT (data, tipo) DO NOTHING`
4. **View**: `config/database.py` creates `cotacao_dolar_selic_pivot` view with columns `data`, `dolar`, `selic_meta`
5. **Visualize**: Streamlit dashboard (`app/app.py`) reads from pivot view, offers 3 granularities (Semana/Mês/Acumulado), Plotly dual-axis charts

### Database Schema

```sql
-- Table
cotacao_dolar_selic (
    id SERIAL PRIMARY KEY,
    data DATE NOT NULL,
    tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('dolar', 'selic', 'selic_meta')),
    valor DECIMAL(10,4) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(data, tipo)
);

-- Pivot View
cotacao_dolar_selic_pivot (
    data,
    dolar,
    selic_meta
)
```

## Common Development Commands

### Local Development (Docker)

```bash
# Start Metabase (BI dashboard on port 3000)
docker compose up -d --build

# Run ETL manually (create tables + fetch/load data)
docker compose exec -T streamlit-app python -c "from config.database import create_tables; create_tables()"
docker compose exec -T streamlit-app python -c "from scripts.etl import load_data; load_data()"

# Streamlit app would run on port 8502 (if streamlit-app service existed in compose)
```

### Python Environment

```bash
# Install dependencies
pip install -r requirements.txt

# Run ETL locally (requires DATABASE_URL in .env)
python -c "from config.database import create_tables; create_tables()"
python -c "from scripts.etl import load_data; load_data()"

# Test BCB API fetch
python -c "from scripts.fetch_bcb_series import fetch_bcb_data; print(fetch_bcb_data('1', 'dolar').head())"
```

### Running the Streamlit Dashboard

```bash
# Requires DATABASE_URL in .env
streamlit run app/app.py
```

### GitHub Actions

The workflow `.github/workflows/update_bcb_series.yml` runs daily at 03:00 UTC. It requires `NEON_DATABASE_URL` secret configured in the `production` environment.

## Key Implementation Details

### Database Connection (`config/database.py`)
- Uses `DATABASE_URL` or `NEON_DATABASE_URL` env var exclusively (no localhost fallback)
- Normalizes URL: strips quotes, removes `channel_binding` param, converts `postgresql://` → `postgresql+psycopg://`
- `pool_pre_ping=True` for Neon pooler resilience
- Creates table + pivot view on `create_tables()`

### BCB API Client (`scripts/fetch_bcb_series.py`)
- Fetches 10 years of data via `dataInicial` / `dataFinal` params
- Retries up to 3 times with exponential backoff (2^attempt seconds)
- Returns DataFrame with columns: `data` (datetime), `valor` (float), `tipo` (str)

### ETL (`scripts/etl.py`)
- Iterates over series: `[("1", "dolar"), ("432", "selic_meta")]`
- Upserts row-by-row with `ON CONFLICT (data, tipo) DO NOTHING` for idempotency
- Prints total records loaded

### Streamlit Dashboard (`app/app.py`)
- **Three granularities**: `semana` (7 days), `mes` (30 days), `acumulado` (monthly average of all data)
- **Dual-axis Plotly chart**: Dólar (left, spline smoothing) + Selic Meta (right, step/hline shape)
- **Selic change detection** in week/month views: only plots points where Selic value changes
- **Statistics table**: count, mean, min, Q1, median, Q3, max, std per series
- **Dark theme** (`paper_bgcolor='#000000'`, `plot_bgcolor='#000000'`)

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `DATABASE_URL` | PostgreSQL connection string (Neon) | Yes (local/prod) |
| `NEON_DATABASE_URL` | Alternative name, used in GitHub Actions | Yes (CI) |

**Never commit `.env`** — it's in `.gitignore`.

## Testing

No formal test suite exists. Manual verification:
1. Run ETL → check `cotacao_dolar_selic` table has recent data
2. Run Streamlit → verify charts render, metrics show latest values
3. Check Metabase at `http://localhost:3000` (after docker compose up)

## Adding a New Series

1. Add entry to `series` list in `scripts/etl.py`: `("SGS_CODE", "tipo_name")`
2. Update `CHECK` constraint in `config/database.py` `create_tables()` to include new `tipo`
3. Update pivot view SQL to include new column
4. Update dashboard (`app/app.py`) to handle new series in charts, metrics, stats

## Notes for Future Work

- The `docker-compose.yml` currently only runs Metabase. The original Streamlit service was removed. If you need Streamlit in Docker, add a `streamlit-app` service back.
- The `Dockerfile` is configured for ETL scripts (CMD runs table creation + ETL), not for serving Streamlit.
- Metabase persists its H2 database in a named volume `metabase_data`.
- BCB API returns data in Portuguese date format (`DD/MM/YYYY`) — parsing is strict.
- Selic Meta (432) is the annualized target rate set by Copom, not the daily Selic over rate.