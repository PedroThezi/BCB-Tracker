import pandas as pd
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
        ("432", "selic_meta")  # Selic meta anualizada (% a.a.), definida pelo Copom
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
    if combined_df.empty:
        raise RuntimeError("Nenhum dado válido foi retornado pela API do BCB para as séries configuradas.")

    combined_df = combined_df.sort_values('data').reset_index(drop=True)

    # Conectar ao banco e carregar
    conn = get_connection()
    cursor = conn.cursor()

    for _, row in combined_df.iterrows():
        try:
            cursor.execute("""
                INSERT INTO cotacao_dolar_selic (data, tipo, valor)
                VALUES (%s, %s, %s)
                ON CONFLICT (data, tipo) DO NOTHING
            """, (row['data'].date(), row['tipo'], row['valor']))
        except Exception as e:
            print(f"Erro ao inserir: {e}")

    conn.commit()
    cursor.close()
    conn.close()

    print(f"Dados carregados com sucesso! Total de registros: {len(combined_df)}")