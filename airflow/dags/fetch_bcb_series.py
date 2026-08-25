# airflow/dags/fetch_bcb_series.py
#
# Mantida para desenvolvimento local / demonstração de orquestração via
# docker-compose. Em produção (Render), quem roda essa mesma lógica é
# scripts/fetch_bcb_series.py, disparado pelo GitHub Actions — ver
# .github/workflows/update_bcb_series.yml.
import os
from datetime import datetime, timedelta

import psycopg2
import requests
from airflow import DAG
from airflow.operators.python import PythonOperator
from psycopg2.extras import execute_batch

DB_CONN = os.getenv("AIRFLOW__CORE__SQL_ALCHEMY_CONN")

SGS_BASE_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados"

# Todas diárias e relacionadas ao câmbio dólar/real
SERIES = {
    "dolar_venda": 1,
    "dolar_compra": 10813,
    "selic_diaria": 11,
    "cdi_diaria": 12,
}


def fetch_and_load_series():
    end_date = datetime.now().strftime("%d/%m/%Y")
    start_date = (datetime.now() - timedelta(days=1825)).strftime("%d/%m/%Y")

    conn = psycopg2.connect(DB_CONN)
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

    total = 0
    for nome_serie, codigo in SERIES.items():
        url = SGS_BASE_URL.format(codigo=codigo)
        params = {"formato": "json", "dataInicial": start_date, "dataFinal": end_date}
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        rows = [
            (nome_serie, datetime.strptime(item["data"], "%d/%m/%Y").date(), float(item["valor"]))
            for item in data
        ]

        execute_batch(
            cursor,
            """
            INSERT INTO bcb_series_data (serie, data, valor) VALUES (%s, %s, %s)
            ON CONFLICT (serie, data) DO UPDATE SET valor = EXCLUDED.valor;
            """,
            rows,
        )
        total += len(rows)
        print(f"Série '{nome_serie}': {len(rows)} registros carregados.")

    conn.commit()
    cursor.close()
    conn.close()
    print(f"Total: {total} registros processados com sucesso.")


dag = DAG(
    "fetch_bcb_series",
    default_args={
        "owner": "data-team",
        "retries": 1,
        "retry_delay": timedelta(minutes=5),
    },
    description="Atualiza diariamente dólar, Selic e CDI (séries diárias do SGS/BCB)",
    schedule_interval="0 0 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
)

fetch_task = PythonOperator(
    task_id="fetch_and_load_bcb_series",
    python_callable=fetch_and_load_series,
    dag=dag,
)

fetch_task
