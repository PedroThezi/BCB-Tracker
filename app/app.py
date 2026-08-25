# app/app.py
import streamlit as st
import os
import psycopg2
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="DolarTracker", layout="wide")

st.title("📊 DolarTracker - Análise de Cotação do Dólar")

# Conectar ao PostgreSQL usando variáveis do .env
DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "dolar_db")
DB_USER = os.getenv("POSTGRES_USER", "airflow")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "airflow")

@st.cache_resource
def get_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    return conn

conn = get_connection()
query = "SELECT data, valor FROM dolar_data ORDER BY data"
df = pd.read_sql(query, conn)

conn.close()

# Gráfico
st.subheader("Cotação do Dólar (BRL/USD) - Últimos 5 anos")
fig = px.line(df, x='data', y='valor', title="Cotação do Dólar ao Longo do Tempo")
st.plotly_chart(fig, use_container_width=True)

# Estatísticas
st.subheader("Estatísticas")
st.write(df.describe())

# Download
st.download_button(
    label="Baixar Dados (CSV)",
    data=df.to_csv(index=False),
    file_name="dolar_data.csv",
    mime="text/csv"
)# app/app.py
import streamlit as st
import os
import psycopg2
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="DolarTracker", layout="wide")

st.title("📊 DolarTracker - Análise de Cotação do Dólar")

DB_HOST = os.getenv("POSTGRES_HOST", "postgres")
DB_PORT = os.getenv("POSTGRES_PORT", "5432")
DB_NAME = os.getenv("POSTGRES_DB", "dolar_db")
DB_USER = os.getenv("POSTGRES_USER", "airflow")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "airflow")

@st.cache_resource
def get_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS
    )
    return conn

conn = get_connection()
query = "SELECT data, valor FROM dolar_data ORDER BY data"
df = pd.read_sql(query, conn)

conn.close()

st.subheader("Cotação do Dólar (BRL/USD) - Últimos 5 anos")
fig = px.line(df, x='data', y='valor', title="Cotação do Dólar ao Longo do Tempo")
st.plotly_chart(fig, use_container_width=True)

st.subheader("Estatísticas")
st.write(df.describe())

st.download_button(
    label="Baixar Dados (CSV)",
    data=df.to_csv(index=False),
    file_name="dolar_data.csv",
    mime="text/csv"
)