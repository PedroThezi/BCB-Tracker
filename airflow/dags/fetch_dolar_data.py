# airflow/dags/fetch_dolar_data.py
#
# Mantida para desenvolvimento local / demonstração de orquestração via
# docker-compose. Em produção (Render), quem roda essa mesma lógica é
# scripts/fetch_dolar_data.py, disparado pelo GitHub Actions — ver
# .github/workflows/update_dolar.yml.
import os
import requests
import psycopg2
from psycopg2.extras import execute_batch
import pandas as pd
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
# Ler variáveis do .env
BCB_API_URL = os.getenv("BCB_API_URL", "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1/dados")
DB_CONN = os.getenv("AIRFLOW__CORE__SQL_ALCHEMY_CONN")

def fetch_data_and_load():
    # Data de 5 anos atrás até hoje
    end_date = datetime.now().strftime("%d/%m/%Y")
    start_date = (datetime.now() - timedelta(days=1825)).strftime("%d/%m/%Y")

    # Fazer requisição (formato=json é obrigatório, senão a API não devolve JSON)
    params = {"formato": "json", "dataInicial": start_date, "dataFinal": end_date}
    response = requests.get(BCB_API_URL, params=params, timeout=30)
    response.raise_for_status()
    data = response.json()

    # Transformar em DataFrame
    df = pd.DataFrame(data)
    df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
    df['valor'] = pd.to_numeric(df['valor'])

    # Conectar ao PostgreSQL
    conn = psycopg2.connect(DB_CONN)
    cursor = conn.cursor()

    # Criar tabela se não existir
    create_table_query = """
    CREATE TABLE IF NOT EXISTS dolar_data (
        data DATE PRIMARY KEY,
        valor NUMERIC
    );
    """
    cursor.execute(create_table_query)

    # Inserir dados
    insert_query = """
    INSERT INTO dolar_data (data, valor) VALUES (%s, %s)
    ON CONFLICT (data) DO UPDATE SET valor = EXCLUDED.valor;
    """
    execute_batch(cursor, insert_query, df[['data', 'valor']].values)

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Dados carregados com sucesso: {len(df)} registros.")

# DAG
dag = DAG(
    'fetch_dolar_data',
    default_args={
        'owner': 'data-team',
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
    },
    description='Atualiza dados do dólar diariamente',
    schedule_interval='0 0 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
)

fetch_task = PythonOperator(
    task_id='fetch_and_load_dolar_data',
    python_callable=fetch_data_and_load,
    dag=dag,
)

fetch_task# airflow/dags/fetch_dolar_data.py
import os
import requests
import psycopg2
from psycopg2.extras import execute_batch
import pandas as pd
from datetime import datetime, timedelta

# Ler variáveis do .env
BCB_API_URL = os.getenv("BCB_API_URL")
DB_CONN = os.getenv("AIRFLOW__CORE__SQL_ALCHEMY_CONN")

def fetch_data_and_load():
    end_date = datetime.now().strftime("%d/%m/%Y")
    start_date = (datetime.now() - timedelta(days=1825)).strftime("%d/%m/%Y")

    url = f"{BCB_API_URL}?dataInicial={start_date}&dataFinal={end_date}"
    response = requests.get(url)
    data = response.json()

    df = pd.DataFrame(data)
    df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')
    df['valor'] = pd.to_numeric(df['valor'])

    conn = psycopg2.connect(DB_CONN)
    cursor = conn.cursor()

    create_table_query = """
    CREATE TABLE IF NOT EXISTS dolar_data (
        data DATE PRIMARY KEY,
        valor NUMERIC
    );
    """
    cursor.execute(create_table_query)

    insert_query = """
    INSERT INTO dolar_data (data, valor) VALUES (%s, %s)
    ON CONFLICT (data) DO UPDATE SET valor = EXCLUDED.valor;
    """
    execute_batch(cursor, insert_query, df[['data', 'valor']].values)

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Dados carregados com sucesso: {len(df)} registros.")

dag = DAG(
    'fetch_dolar_data',
    default_args={
        'owner': 'data-team',
        'retries': 1,
        'retry_delay': timedelta(minutes=5),
    },
    description='Atualiza dados do dólar diariamente',
    schedule_interval='0 0 * * *',
    start_date=datetime(2024, 1, 1),
    catchup=False,
)

fetch_task = PythonOperator(
    task_id='fetch_and_load_dolar_data',
    python_callable=fetch_data_and_load,
    dag=dag,
)

fetch_task