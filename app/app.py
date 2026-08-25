import streamlit as st
import pandas as pd
from config.database import get_connection as database_connection

# Configuração da página (deve ser o primeiro comando Streamlit)
st.set_page_config(page_title="📊 DolarTracker", layout="wide")

def get_connection():
    return database_connection()

def fetch_data():
    """Busca os dados do banco de dados."""
    try:
        conn = get_connection()
        # Usamos aspas triplas para queries de múltiplas linhas
        query = """
            SELECT data, valor, tipo 
            FROM cotacao_dolar_selic 
            ORDER BY data DESC
            LIMIT 1000;
        """
        df = pd.read_sql(query, conn)
        conn.close()
        
        # Garantir que a coluna 'data' seja datetime para o gráfico não quebrar
        if not df.empty:
            df['data'] = pd.to_datetime(df['data'])
            
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame(columns=['data', 'valor', 'tipo'])

# --- INTERFACE DO USUÁRIO ---

st.title("🏦 DolarTracker – Análise de Cotação do Dólar e Selic (5 anos)")

# Carregar dados
df = fetch_data()

if df.empty:
    st.warning("Nenhum dado encontrado no banco de dados. Certifique-se de rodar o script de ETL primeiro.")
else:
    # Sidebar ou Filtro na tela principal
    st.sidebar.header("Filtros")
    tipo_selecionado = st.sidebar.selectbox(
        "Selecione o tipo de dado", 
        ["Todos", "dolar", "selic"], 
        index=0
    )

    # Lógica de filtragem (ajustada para bater com o que salvamos no banco)
    if tipo_selecionado != "Todos":
        # Usamos .str.lower() para evitar erro de caixa alta/baixa
        df = df[df['tipo'].str.lower() == tipo_selecionado.lower()]

    # Layout de Colunas para métricas rápidas (Opcional - Dá um ar de BI Profissional)
    col1, col2 = st.columns(2)
    if not df.empty:
        ultimo_valor = df.iloc[0]['valor']
        ultima_data = df.iloc[0]['data'].strftime('%d/%m/%Y')
        col1.metric("Último Valor Registrado", f"R$ {ultimo_valor:,.2f}", help=f"Data: {ultima_data}")

    # Exibir gráfico
    st.subheader(f"📈 Evolução Histórica: {tipo_selecionado.capitalize()}")
    # O Streamlit precisa que o index seja a data para o line_chart funcionar bem
    chart_data = df.set_index('data')[['valor']]
    st.line_chart(chart_data)

    # Tabela de dados
    with st.expander("🔍 Visualizar tabela de dados brutos"):
        st.dataframe(df, use_container_width=True)