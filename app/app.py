# app/app.py
import os
from urllib.parse import urlparse

import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st

st.set_page_config(page_title="Dólar Tracker", layout="centered")

st.title("📈 Dólar, Selic e CDI")
st.caption("Séries diárias do SGS/BCB relacionadas ao câmbio dólar/real.")

# O Render injeta variáveis de ambiente, não um secrets.toml — por isso
# lemos de os.environ primeiro. st.secrets fica só como fallback para
# rodar localmente com o Streamlit fora do docker-compose.
DATABASE_URL = os.environ.get("DATABASE_URL") or st.secrets.get("DATABASE_URL", "")

if not DATABASE_URL:
    st.error("❌ DATABASE_URL não configurada.")
    st.stop()

SERIES_LABELS = {
    "dolar_venda": "Dólar (venda)",
    "dolar_compra": "Dólar (compra)",
    "selic_diaria": "Selic (diária)",
    "cdi_diaria": "CDI (diária)",
}


@st.cache_data(ttl=3600)
def load_data():
    result = urlparse(DATABASE_URL)
    conn = psycopg2.connect(
        host=result.hostname,
        port=result.port,
        database=result.path[1:],  # Remove leading '/'
        user=result.username,
        password=result.password,
    )
    df = pd.read_sql(
        "SELECT serie, data, valor FROM bcb_series_data ORDER BY data", conn
    )
    conn.close()
    return df


try:
    df = load_data()

    if df.empty:
        st.warning("Ainda não há dados na tabela. Aguarde a primeira execução do ETL.")
        st.stop()

    disponiveis = [s for s in SERIES_LABELS if s in df["serie"].unique()]
    escolhidas = st.multiselect(
        "Séries para exibir",
        options=disponiveis,
        default=["dolar_venda"] if "dolar_venda" in disponiveis else disponiveis[:1],
        format_func=lambda s: SERIES_LABELS.get(s, s),
    )

    if not escolhidas:
        st.info("Selecione ao menos uma série.")
        st.stop()

    df_filtrado = df[df["serie"].isin(escolhidas)].copy()
    df_filtrado["serie"] = df_filtrado["serie"].map(SERIES_LABELS)

    fig = px.line(
        df_filtrado,
        x="data",
        y="valor",
        color="serie",
        labels={"data": "Data", "valor": "Valor", "serie": "Série"},
    )
    st.plotly_chart(fig, use_container_width=True)

    st.dataframe(
        df_filtrado.rename(columns={"serie": "Série", "data": "Data", "valor": "Valor"}),
        use_container_width=True,
    )

except Exception as e:
    st.error(f"❌ Erro ao conectar ao banco: {e}")

st.markdown("---")
st.caption("Dados atualizados automaticamente 1x por dia via GitHub Actions.")
