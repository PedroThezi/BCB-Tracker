import psycopg2
import os
from dotenv import load_dotenv

# Carrega o arquivo .env apenas se estiver rodando localmente
load_dotenv()

def get_connection():
    """
    Retorna uma conexão com o PostgreSQL.
    Exige explicitamente DATABASE_URL para evitar tentaivas de conexão local em CI/produção.
    """
    try:
        database_url = os.getenv("DATABASE_URL")

        if not database_url:
            raise RuntimeError(
                "DATABASE_URL não configurada. "
                "Em desenvolvimento use o arquivo .env local; em GitHub Actions use a secret NEON_DATABASE_URL. "
                "Não há fallback para localhost."
            )

        return psycopg2.connect(database_url)

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