import os
import re
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# Carrega o .env apenas em execução local; em CI/containers a config vem do ambiente.
load_dotenv()


def normalize_database_url(database_url):
    """Normaliza a URL do PostgreSQL antes de criar o engine SQLAlchemy.

    - Remove aspas e espaços acidentais.
    - Descarta `channel_binding` (psycopg não aceita via string de conexão).
    - Força o driver `psycopg` (v3) para um esquema `postgresql://`.
    """
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
    """Cria um engine SQLAlchemy a partir de DATABASE_URL (ou NEON_DATABASE_URL).

    Não há fallback para localhost: em CI/produção, a falta da variável é um
    erro de configuração e deve falhar imediatamente. O pooler do Neon faz
    balanceamento por DNS, então conectamos sempre pelo hostname (sem
    `hostaddr` fixo) para evitar SNI/IP inconsistentes entre requisições.
    """
    database_url = os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "DATABASE_URL não configurada. "
            "Configure DATABASE_URL ou NEON_DATABASE_URL no ambiente do serviço. "
            "Não há fallback para localhost."
        )

    return create_engine(
        normalize_database_url(database_url),
        pool_pre_ping=True
    )


def get_connection():
    """Abre uma conexão com o PostgreSQL, exigindo DATABASE_URL explícita."""
    return get_engine().connect()


def create_tables():
    """Cria a tabela `cotacao_dolar_selic` e a view pivotada, se ausentes."""
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
        conn.execute(text("""
        CREATE OR REPLACE VIEW cotacao_dolar_selic_pivot AS
        WITH base AS (
            SELECT
                data,
                MAX(CASE WHEN tipo = 'dolar' THEN valor END) AS dolar,
                MAX(CASE WHEN tipo = 'selic_meta' THEN valor END) AS selic_meta
            FROM cotacao_dolar_selic
            GROUP BY data
            HAVING COUNT(*) > 0
        )
        SELECT
            data,
            dolar,
            selic_meta,
            CASE
                WHEN dolar IS NULL OR LAG(dolar) OVER (ORDER BY data) IS NULL THEN NULL
                WHEN LAG(dolar) OVER (ORDER BY data) = 0 THEN NULL
                ELSE ((dolar - LAG(dolar) OVER (ORDER BY data))
                      / LAG(dolar) OVER (ORDER BY data)) * 100
            END AS dolar_variacao,
            CASE
                WHEN selic_meta IS NULL OR LAG(selic_meta) OVER (ORDER BY data) IS NULL THEN NULL
                WHEN LAG(selic_meta) OVER (ORDER BY data) = 0 THEN NULL
                ELSE ((selic_meta - LAG(selic_meta) OVER (ORDER BY data))
                      / LAG(selic_meta) OVER (ORDER BY data)) * 100
            END AS selic_meta_variacao
        FROM base
        ORDER BY data;
        """))
    engine.dispose()