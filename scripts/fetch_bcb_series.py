import requests
import pandas as pd
from datetime import datetime, timedelta
import time


def fetch_bcb_data(codigo_serie: str, nome_serie: str) -> pd.DataFrame:
    """
    Coleta dados de uma série do Banco Central do Brasil (API pública).

    Args:
        codigo_serie (str): Código da série no formato 'bcdata.sgs.{codigo}'
        nome_serie (str): Nome da série para identificação ('dolar', 'selic', etc.)

    Returns:
        pd.DataFrame: DataFrame com colunas ['data', 'valor', 'tipo']
    """
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo_serie}/dados"

    params = {
        "formato": "json",
        "dataInicial": (datetime.now() - timedelta(days=365 * 10)).strftime("%d/%m/%Y"),
        "dataFinal": datetime.now().strftime("%d/%m/%Y")
    }

    last_error = None

    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=20)
            if response.status_code != 200:
                raise Exception(f"Erro na API: {response.status_code} - {response.text}")

            data = response.json()
            if not isinstance(data, list):
                raise Exception(data.get("message", "Resposta inesperada da API"))

            if not data:
                print(f"Aviso: a série {nome_serie} (código {codigo_serie}) retornou vazio.")
                return pd.DataFrame(columns=['data', 'valor', 'tipo'])

            df = pd.DataFrame(data)
            if 'data' not in df.columns or 'valor' not in df.columns:
                raise ValueError(f"Formato inesperado da resposta para {nome_serie}: colunas ausentes.")

            df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce')
            df['valor'] = pd.to_numeric(df['valor'], errors='coerce')
            df = df.dropna(subset=['data', 'valor']).copy()
            df['tipo'] = nome_serie

            return df[['data', 'valor', 'tipo']]
        except Exception as e:
            last_error = e
            if attempt < 2:
                time.sleep(2 ** attempt)
                continue

    print(f"Erro ao buscar dados da série {nome_serie} (código {codigo_serie}): {last_error}")
    return pd.DataFrame(columns=['data', 'valor', 'tipo'])

# ==================== EXEMPLOS DE USO ====================
if __name__ == "__main__":
    # Coletar dólar (Série 1)
    dolar_data = fetch_bcb_data("1", "dolar")
    print("Dólar coletado:", len(dolar_data), "registros")

    # Coletar Selic meta anualizada (Série 432)
    selic_data = fetch_bcb_data("432", "selic_meta")
    print("Selic Meta coletada:", len(selic_data), "registros")

    # Juntar
    combined = pd.concat([dolar_data, selic_data], ignore_index=True)
    print("Total de registros:", len(combined))