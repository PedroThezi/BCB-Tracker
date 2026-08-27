import pandas as pd
from decimal import Decimal
from config.database import get_connection
from scripts.fetch_bcb_series import fetch_bcb_data

def load_data():
    """
    Carrega dados do dólar e da selic usando o script único.
    """
    print("Iniciando ETL...")

    # Lista de séries para coletar
    series = [
        ("1", "dolar"),
        ("11", "selic")
    ]

    all_data = []
    for codigo, nome in series:
        df = fetch_bcb_data(codigo, nome)
        if not df.empty:
            all_data.append(df)

    if not all_data:
        raise RuntimeError("Nenhuma série foi coletada do BCB")

    # Concatenar todos os dados
    combined_df = pd.concat(all_data, ignore_index=True)
    combined_df = combined_df.sort_values('data').reset_index(drop=True)

    # Conectar ao banco e carregar
    conn = get_connection()
    cursor = conn.cursor()

    for _, row in combined_df.iterrows():
        try:
            cursor.execute("""
                INSERT INTO cotacao_dolar_selic (data, tipo, valor)
                VALUES (%s, %s, %s)
                ON CONFLICT (data, tipo) DO UPDATE
                SET valor = EXCLUDED.valor
            """, (row['data'].date(), row['tipo'], Decimal(str(row['valor']))))
        except Exception as e:
            print(f"Erro ao inserir: {e}")

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Dados carregados com sucesso! Total de registros: {len(combined_df)}")