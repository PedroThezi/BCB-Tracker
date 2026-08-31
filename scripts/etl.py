import pandas as pd
from sqlalchemy import text

from config.database import get_engine
from scripts.fetch_bcb_series import fetch_bcb_data


# (código SGS, tipo armazenado). Selic Meta (432) é a taxa alvo anualizada
# definida pelo Copom, não a taxa over diária.
SERIES = [
    ("1", "dolar"),
    ("432", "selic_meta"),
]


def load_data():
    """Coleta cada série no BCB e faz upsert idempotente no PostgreSQL."""
    print("Iniciando ETL...")

    frames = [fetch_bcb_data(codigo, nome) for codigo, nome in SERIES]
    valid = [df for df in frames if not df.empty]
    if not valid:
        raise RuntimeError("Nenhuma série foi coletada do BCB")

    combined = (
        pd.concat(valid, ignore_index=True)
        .sort_values("data")
        .reset_index(drop=True)
    )

    # psycopg aceita `date`/`numeric` a partir de `datetime`/`Decimal`/strings
    # ISO, mas converter explicitamente evita ambiguidade de tipo no driver.
    rows = [
        {"data": d.date(), "tipo": t, "valor": float(v)}
        for d, t, v in combined[["data", "tipo", "valor"]].itertuples(index=False, name=None)
    ]

    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO cotacao_dolar_selic (data, tipo, valor)
                VALUES (:data, :tipo, :valor)
                ON CONFLICT (data, tipo) DO NOTHING
            """),
            rows,
        )
    engine.dispose()

    print(f"Dados carregados com sucesso! Total de registros: {len(combined)}")
