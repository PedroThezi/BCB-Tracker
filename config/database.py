import os
import re
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Carrega o arquivo .env apenas se estiver rodando localmente
load_dotenv()


def normalize_database_url(database_url):
    """Normaliza a URL do PostgreSQL antes de criar o engine SQLAlchemy."""
    if not database_url:
        return database_url

    normalized = database_url.strip().strip("'\"").strip()
    normalized = re.sub(r'([?&])channel_binding=[^&]+', r'\1', normalized)
    normalized = normalized.replace('?&', '?').rstrip('&')

    if normalized.endswith('?'):
        normalized = normalized[:-1]

    normalized = re.sub(
        r'^postgresql://',
        'postgresql+psycopg://',
        normalized
    )

    return normalized


def get_engine():
    """Cria um engine SQLAlchemy usando exclusivamente DATABASE_URL."""
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL não configurada. "
            "Em desenvolvimento use o arquivo .env local; em GitHub Actions use a secret NEON_DATABASE_URL. "
            "Não há fallback para localhost."
        )

    return create_engine(
        normalize_database_url(database_url),
        pool_pre_ping=True
    )


def get_connection():
    """
    Retorna uma conexão com o PostgreSQL.
    Exige explicitamente DATABASE_URL para evitar tentaivas de conexão local em CI/produção.
    """
    try:
        return get_engine().connect()

    except Exception as e:
        print(f"❌ Erro ao conectar ao banco de dados: {e}")
        raise e

def create_tables():
    """Cria a tabela e a view pivotada necessárias caso não existam."""
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("""
        CREATE TABLE IF NOT EXISTS cotacao_dolar_selic (
            id SERIAL PRIMARY KEY,
            data DATE NOT NULL,
            tipo VARCHAR(20) NOT NULL CHECK (tipo IN ('dolar', 'selic', 'selic_meta')),
            valor DECIMAL(10,4) NOT NULL,
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(data, tipo)
        );
        """))
        conn.execute(text("DROP VIEW IF EXISTS cotacao_dolar_selic_pivot;"))
        conn.execute(text("""
        CREATE VIEW cotacao_dolar_selic_pivot AS
        SELECT
            data,
            MAX(CASE WHEN tipo = 'dolar' THEN valor END) AS dolar,
            MAX(CASE WHEN tipo = 'selic_meta' THEN valor END) AS selic_meta
        FROM cotacao_dolar_selic
        GROUP BY data
        HAVING COUNT(*) > 0
        ORDER BY data;
        """))
    engine.dispose()