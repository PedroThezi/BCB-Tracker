# app/app.py
import streamlit as st
import pandas as pd
import psycopg2
from urllib.parse import urlparse

st.set_page_config(page_title="Dólar Tracker", layout="centered")

st.title("📈 Histórico do Dólar")

# Conectar ao banco no Render (via URL de conexão)
DATABASE_URL = st.secrets["DATABASE_URL"]  # Render seta isso automaticamente

try:
    # Parse a URL do banco
    result = urlparse(DATABASE_URL)
    conn = psycopg2.connect(
        host=result.hostname,
        port=result.port,
        database=result.path[1:],  # Remove leading '/'
        user=result.username,
        password=result.password
    )

    query = "SELECT data, valor FROM dolar_data ORDER BY data"
    df = pd.read_sql(query, conn)
    conn.close()

    st.dataframe(df, use_container_width=True)

except Exception as e:
    st.error(f"❌ Erro ao conectar ao banco: {e}")

st.markdown("---")
st.caption("Dados atualizados automaticamente.")