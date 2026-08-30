import requests
import pandas as pd
from datetime import datetime, timedelta
import time


COLUNAS_VAZIAS = pd.DataFrame(columns=['data', 'valor', 'tipo'])


def fetch_bcb_data(codigo_serie: str, nome_serie: str) -> pd.DataFrame:
    """Coleta os últimos 10 anos de uma série SGS do BCB.

    Retorna DataFrame com colunas ['data', 'valor', 'tipo']. Em caso de
    falha após 3 tentativas, retorna um DataFrame vazio e registra o erro.
    """
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo_serie}/dados"
    params = {
        "formato": "json",
        "dataInicial": (datetime.now() - timedelta(days=365 * 10)).strftime("%d/%m/%Y"),
        "dataFinal": datetime.now().strftime("%d/%m/%Y")
    }

    last_error: Exception | None = None
    with requests.Session() as session:
        for attempt in range(3):
            try:
                response = session.get(url, params=params, timeout=20)
                if response.status_code != 200:
                    raise Exception(f"Erro na API: {response.status_code} - {response.text}")

                data = response.json()
                if not isinstance(data, list):
                    raise Exception(data.get("message", "Resposta inesperada da API"))

                if not data:
                    print(f"Aviso: a série {nome_serie} (código {codigo_serie}) retornou vazio.")
                    return COLUNAS_VAZIAS.copy()

                df = pd.DataFrame(data)
                if 'data' not in df.columns or 'valor' not in df.columns:
                    raise ValueError(
                        f"Formato inesperado da resposta para {nome_serie}: colunas ausentes."
                    )

                df['data'] = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce')
                df['valor'] = pd.to_numeric(df['valor'], errors='coerce')
                df = df.dropna(subset=['data', 'valor']).copy()
                df['tipo'] = nome_serie

                return df[['data', 'valor', 'tipo']]
            except Exception as e:
                last_error = e
                if attempt < 2:
                    time.sleep(2 ** attempt)

    print(
        f"Erro ao buscar dados da série {nome_serie} (código {codigo_serie}): {last_error}"
    )
    return COLUNAS_VAZIAS.copy()


if __name__ == "__main__":
    dolar_data = fetch_bcb_data("1", "dolar")
    print("Dólar coletado:", len(dolar_data), "registros")

    selic_data = fetch_bcb_data("432", "selic_meta")
    print("Selic Meta coletada:", len(selic_data), "registros")

    combined = pd.concat([dolar_data, selic_data], ignore_index=True)
    print("Total de registros:", len(combined))