#!/usr/bin/env python3
"""
scripts/fetch_bcb_series.py

Extrai, dos últimos N anos, todas as séries diárias do SGS/BCB
relacionadas ao dólar (mesma cadência de atualização: diária, dias
úteis) e faz upsert em uma tabela única no formato "tidy"
(serie, data, valor).

Séries incluídas (todas diárias e ligadas ao mercado de câmbio):
    1     Dólar comercial - venda (PTAX)
    10813 Dólar comercial - compra (PTAX)
    11    Selic - taxa diária (overnight)
    12    CDI - taxa diária (overnight)

Pensado para rodar como script standalone — sem depender do Airflow
estar no ar — disparado pelo GitHub Actions
(.github/workflows/update_bcb_series.yml) ou manualmente em dev.

Variáveis de ambiente esperadas:
    DATABASE_URL   Connection string do Postgres. No Render, use a
                    "External Database URL".
"""

import os
import sys
from datetime import datetime, timedelta
from urllib.parse import urlparse

import pandas as pd
import psycopg2
import requests
from psycopg2.extras import execute_batch

SGS_BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

# Todas as séries abaixo são diárias (dias úteis) e diretamente
# relacionadas ao câmbio dólar/real.
SERIES = {
    "dolar_venda": 1,
    "dolar_compra": 10813,
    "selic_diaria": 11,
    "cdi_diaria": 12,
}


def get_db_connection():
    """Conecta ao Postgres a partir de DATABASE_URL (formato Render) ou
    das variáveis POSTGRES_* separadas (formato docker-compose local)."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        result = urlparse(database_url)
        return psycopg2.connect(
            host=result.hostname,
            port=result.port,
            dbname=result.path.lstrip("/"),
            user=result.username,
            password=result.password,
            sslmode="require",
        )

    # Fallback para desenvolvimento local via docker-compose
    return psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=os.getenv("POSTGRES_PORT", "5432"),
        dbname=os.getenv("POSTGRES_DB", "dolar_db"),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
    )


def fetch_series(codigo_serie: int, years: int = 5) -> pd.DataFrame:
    """Busca uma série do SGS/BCB dos últimos N anos."""
    url = SGS_BASE_URL.format(codigo=codigo_serie)

    end_date = datetime.now().strftime("%d/%m/%Y")
    start_date = (datetime.now() - timedelta(days=365 * years)).strftime("%d/%m/%Y")

    params = {
        "formato": "json",
        "dataInicial": start_date,
        "dataFinal": end_date,
    }

    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if not data:
        raise ValueError(f"Série {codigo_serie}: API do BCB retornou vazio.")

    df = pd.DataFrame(data)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = pd.to_numeric(df["valor"])
    return df


def upsert_series_data(nome_serie: str, df: pd.DataFrame) -> int:
    """Cria a tabela tidy se necessário e faz upsert dos registros de uma série."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS bcb_series_data (
            serie VARCHAR(50) NOT NULL,
            data DATE NOT NULL,
            valor NUMERIC(12, 6) NOT NULL,
            PRIMARY KEY (serie, data)
        );
        """
    )

    rows = [(nome_serie, row.data, row.valor) for row in df.itertuples()]

    execute_batch(
        cursor,
        """
        INSERT INTO bcb_series_data (serie, data, valor) VALUES (%s, %s, %s)
        ON CONFLICT (serie, data) DO UPDATE SET valor = EXCLUDED.valor;
        """,
        rows,
    )

    conn.commit()
    cursor.close()
    conn.close()
    return len(rows)


def main():
    total = 0
    for nome_serie, codigo in SERIES.items():
        print(f"Buscando série '{nome_serie}' (código {codigo}) na API do BCB...")
        df = fetch_series(codigo, years=5)
        row_count = upsert_series_data(nome_serie, df)
        print(f"  -> {row_count} registros gravados.")
        total += row_count
    print(f"Concluído: {total} registros processados no total.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Falha na atualização das séries do BCB: {exc}", file=sys.stderr)
        sys.exit(1)
