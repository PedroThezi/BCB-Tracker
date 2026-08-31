"""Camada de acesso a dados do dashboard.

Lê a view `cotacao_dolar_selic_pivot` e devolve DataFrames no formato
apropriado para as visualizações.
"""
import pandas as pd
from sqlalchemy import text

from config.database import get_connection


# Colunas lidas da view pivotada.
PIVOT_COLUMNS = ["data", "dolar", "selic_meta", "dolar_variacao", "selic_meta_variacao"]
NUMERIC_COLUMNS = ["dolar", "selic_meta", "dolar_variacao", "selic_meta_variacao"]


def fetch_data():
    """Carrega a série histórica a partir da view pivotada.

    Retorna `(df, error)` onde `error` é `None` em caso de sucesso.
    """
    query = text("""
        SELECT data, dolar, selic_meta, dolar_variacao, selic_meta_variacao
        FROM cotacao_dolar_selic_pivot
        ORDER BY data;
    """)
    empty = pd.DataFrame(columns=PIVOT_COLUMNS)
    try:
        with get_connection() as conn:
            df = pd.read_sql(query, conn)
    except Exception as e:
        return empty, f"Erro ao carregar a view: {e}"

    if df.empty:
        return empty, None

    df["data"] = pd.to_datetime(df["data"])
    # psycopg devolve `numeric` como Decimal; convertemos para float para que
    # Plotly e os formatadores operem diretamente.
    for col in NUMERIC_COLUMNS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df, None


def build_long_df(pivot_df):
    """Converte o pivot (1 linha por data) em long (1 linha por data+série),
    preservando a variação calculada pela view."""
    series_map = (
        ("dolar", "dolar", "dolar_variacao"),
        ("selic_meta", "selic_meta", "selic_meta_variacao"),
    )
    parts = []
    for tipo, valor_col, variacao_col in series_map:
        parts.append(
            pivot_df[["data", valor_col, variacao_col]]
            .rename(columns={valor_col: "valor", variacao_col: "variacao"})
            .assign(tipo=tipo)
        )
    long = (
        pd.concat(parts, ignore_index=True)
        .dropna(subset=["valor"])
        .assign(data_dt=lambda d: pd.to_datetime(d["data"], errors="coerce"))
        .dropna(subset=["data_dt"])
        .sort_values(["data_dt", "tipo"], ascending=[False, True])
        .reset_index(drop=True)
    )
    long["data"] = long["data_dt"].dt.strftime("%d/%m/%Y")
    return long
