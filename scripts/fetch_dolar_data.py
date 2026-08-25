#!/usr/bin/env python3
"""
scripts/fetch_dolar_data.py

Extrai a cotação diária do dólar (série 1 do SGS/BCB) dos últimos 5 anos
e faz upsert no PostgreSQL.

Pensado para rodar como script standalone — sem depender do Airflow
estar no ar — para ser disparado pelo GitHub Actions (ver
.github/workflows/update_dolar.yml) ou manualmente em dev.

Variáveis de ambiente esperadas:
    DATABASE_URL   Connection string do Postgres (formato
                    postgresql://user:pass@host:port/dbname).
                    No Render, use a "External Database URL".
    BCB_API_URL    Opcional. Default aponta para a série 1 (dólar venda).
"""

import os
import sys
from datetime import datetime, timedelta
from urllib.parse import urlparse

import pandas as pd
import psycopg2
import requests
from psycopg2.extras import execute_batch

DEFAULT_BCB_API_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados"


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


def fetch_dolar_series(years: int = 5) -> pd.DataFrame:
    """Busca a série do dólar dos últimos N anos na API do BCB."""
    api_url = os.getenv("BCB_API_URL", DEFAULT_BCB_API_URL)

    end_date = datetime.now().strftime("%d/%m/%Y")
    start_date = (datetime.now() - timedelta(days=365 * years)).strftime("%d/%m/%Y")

    params = {
        "formato": "json",
        "dataInicial": start_date,
        "dataFinal": end_date,
    }

    response = requests.get(api_url, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    if not data:
        raise ValueError("API do BCB retornou vazio — confira o intervalo de datas.")

    df = pd.DataFrame(data)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = pd.to_numeric(df["valor"])
    return df


def upsert_dolar_data(df: pd.DataFrame) -> int:
    """Cria a tabela se necessário e faz upsert dos registros."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dolar_data (
            data DATE PRIMARY KEY,
            valor NUMERIC(10, 4) NOT NULL
        );
        """
    )

    execute_batch(
        cursor,
        """
        INSERT INTO dolar_data (data, valor) VALUES (%s, %s)
        ON CONFLICT (data) DO UPDATE SET valor = EXCLUDED.valor;
        """,
        df[["data", "valor"]].values,
    )

    conn.commit()
    row_count = len(df)
    cursor.close()
    conn.close()
    return row_count


def main():
    print("Buscando dados do dólar na API do BCB...")
    df = fetch_dolar_series(years=5)
    print(f"{len(df)} registros recebidos. Gravando no banco...")
    row_count = upsert_dolar_data(df)
    print(f"Concluído: {row_count} registros processados com sucesso.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Falha na atualização dos dados do dólar: {exc}", file=sys.stderr)
        sys.exit(1)
