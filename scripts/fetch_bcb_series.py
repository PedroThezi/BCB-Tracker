import time
from datetime import datetime, timedelta

import pandas as pd
import requests


# Colunas padronizadas em todos os retornos de `fetch_bcb_data` (inclusive vazio).
EMPTY_DF = pd.DataFrame(columns=["data", "valor", "tipo"])


def fetch_bcb_data(codigo_serie: str, nome_serie: str) -> pd.DataFrame:
    """Coleta os últimos 10 anos de uma série SGS do BCB.

    Retorna DataFrame com colunas ['data', 'valor', 'tipo']. Após 3 tentativas
    com backoff exponencial, retorna DataFrame vazio e registra o erro.
    """
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo_serie}/dados"
    params = {
        "formato": "json",
        "dataInicial": (datetime.now() - timedelta(days=365 * 10)).strftime("%d/%m/%Y"),
        "dataFinal": datetime.now().strftime("%d/%m/%Y"),
    }

    last_error = None
    with requests.Session() as session:
        for attempt in range(3):
            try:
                response = session.get(url, params=params, timeout=20)
                if response.status_code != 200:
                    raise RuntimeError(
                        f"Erro na API: {response.status_code} - {response.text}"
                    )

                payload = response.json()
                if not isinstance(payload, list):
                    raise RuntimeError(payload.get("message", "Resposta inesperada da API"))
                if not payload:
                    print(f"Aviso: série {nome_serie} (código {codigo_serie}) retornou vazio.")
                    return EMPTY_DF.copy()

                df = pd.DataFrame(payload)
                if "data" not in df.columns or "valor" not in df.columns:
                    raise ValueError(
                        f"Formato inesperado para {nome_serie}: colunas ausentes."
                    )

                df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
                df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
                df = df.dropna(subset=["data", "valor"]).copy()
                df["tipo"] = nome_serie
                return df[["data", "valor", "tipo"]]
            except Exception as e:
                last_error = e
                if attempt < 2:
                    time.sleep(2 ** attempt)

    print(f"Erro ao buscar série {nome_serie} (código {codigo_serie}): {last_error}")
    return EMPTY_DF.copy()
