import os

import pandas as pd
import plotly.express as px
import psycopg2
import streamlit as st


# ============================================================
# CONFIGURAÇÃO DO STREAMLIT
# ============================================================

st.set_page_config(
    page_title="DolarTracker",
    layout="wide"
)


# ============================================================
# CONFIGURAÇÃO DO BANCO
# ============================================================

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "dolar_db")
DB_USER = os.getenv("POSTGRES_USER", "airflow")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "airflow")


# ============================================================
# CONEXÃO COM POSTGRESQL
# ============================================================

@st.cache_resource
def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )


# ============================================================
# CARREGAMENTO DOS DADOS
# ============================================================

@st.cache_data
def load_data():
    conn = get_connection()

    query = """
        SELECT data, valor
        FROM dolar_data
        ORDER BY data
    """

    return pd.read_sql(query, conn)


df = load_data()


# ============================================================
# TÍTULO
# ============================================================

st.title("📊 DolarTracker - Análise de Cotação do Dólar")


# ============================================================
# GRÁFICO
# ============================================================

st.subheader("Cotação do Dólar (BRL/USD) - Últimos 5 anos")

fig = px.line(
    df,
    x="data",
    y="valor",
    title="Cotação do Dólar ao Longo do Tempo"
)

fig.update_layout(
    xaxis_title="Data",
    yaxis_title="Valor (R$)",
    hovermode="x unified"
)

st.plotly_chart(
    fig,
    use_container_width=True
)


# ============================================================
# ESTATÍSTICAS
# ============================================================

st.subheader("Estatísticas")

st.write(df.describe())


# ============================================================
# DOWNLOAD
# ============================================================

st.download_button(
    label="Baixar Dados (CSV)",
    data=df.to_csv(index=False),
    file_name="dolar_data.csv",
    mime="text/csv"
)