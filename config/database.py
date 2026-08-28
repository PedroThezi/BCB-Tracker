import psycopg2
import os
from dotenv import load_dotenv

# Carrega o arquivo .env apenas se estiver rodando localmente
load_dotenv()

def get_connection():
    """
    Retorna uma conexão com o PostgreSQL.
    Busca as credenciais nas variáveis de ambiente (Docker ou Render).
    """
    try:
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            conn = psycopg2.connect(database_url)
        else:
            conn = psycopg2.connect(
                host=os.getenv("POSTGRES_HOST", "localhost"),
                port=os.getenv("POSTGRES_PORT", "5432"),
                database=os.getenv("POSTGRES_DB", "dolartracker_db"),
                user=os.getenv("POSTGRES_USER", "airflow_user"),
                password=os.getenv("POSTGRES_PASSWORD", "supersecret")
            )
        return conn
    except Exception as e:
        print(f"❌ Erro ao conectar ao banco de dados: {e}")
        raise e

def create_tables():
    """Cria a tabela e a view pivotada necessárias caso não existam."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS cotacao_dolar_selic (
            id SERIAL PRIMARY KEY,
            data DATE NOT NULL,
            tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('dolar', 'selic', 'selic_meta')),
            valor DECIMAL(10,4) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(data, tipo)
        );
    """)
    cursor.execute("DROP VIEW IF EXISTS cotacao_dolar_selic_pivot;")
    cursor.execute("""
        CREATE VIEW cotacao_dolar_selic_pivot AS
        SELECT
            data,
            MAX(CASE WHEN tipo = 'dolar' THEN valor END) AS dolar,
            MAX(CASE WHEN tipo = 'selic_meta' THEN valor END) AS selic_meta
        FROM cotacao_dolar_selic
        GROUP BY data
        HAVING COUNT(*) > 0
        ORDER BY data;
    """)
    conn.commit()
    cursor.close()
    conn.close()