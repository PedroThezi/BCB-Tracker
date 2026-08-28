import requests
import pandas as pd
from datetime import datetime, timedelta

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
        "dataInicial": (datetime.now() - timedelta(days=3652)).strftime("%d/%m/%Y"),
        "dataFinal": datetime.now().strftime("%d/%m/%Y")
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            raise Exception(f"Erro na API: {response.status_code} - {response.text}")

        data = response.json()
        if not isinstance(data, list):
            raise Exception(data.get("message", "Resposta inesperada da API"))
        df = pd.DataFrame(data)

        # Converter data para datetime
        df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y')

        # Limpar e converter valor
        df['valor'] = pd.to_numeric(df['valor'], errors='coerce')
        df = df.dropna(subset=['valor']).copy()

        # Adicionar tipo
        df['tipo'] = nome_serie

        return df[['data', 'valor', 'tipo']]

    except Exception as e:
        print(f"Erro ao buscar dados da série {nome_serie} (código {codigo_serie}): {e}")
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