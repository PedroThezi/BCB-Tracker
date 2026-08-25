import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
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

def fetch_pivot_data():
    """Busca os dados pivotados para o gráfico mensal."""
    try:
        conn = get_connection()
        query = """
            SELECT data, dolar, selic
            FROM cotacao_dolar_selic_pivot
            ORDER BY data;
        """
        df = pd.read_sql(query, conn)
        conn.close()

        if not df.empty:
            df['data'] = pd.to_datetime(df['data'])

        return df
    except Exception as e:
        st.error(f"Erro ao carregar a série pivotada: {e}")
        return pd.DataFrame(columns=['data', 'dolar', 'selic'])

def build_monthly_chart(df):
    """Cria o gráfico com médias mensais de dólar e Selic."""
    monthly = (
        df.set_index('data')[['dolar', 'selic']]
        .resample('M')
        .mean()
        .dropna(how='all')
        .reset_index()
    )
    monthly['mes_ano'] = monthly['data'].dt.strftime('%m/%Y')

    figure = make_subplots(specs=[[{'secondary_y': True}]])
    figure.add_trace(
        go.Scatter(
            x=monthly['mes_ano'],
            y=monthly['dolar'],
            mode='lines+markers',
            name='Dólar',
            line={'color': '#1f77b4'}
        ),
        secondary_y=False
    )
    figure.add_trace(
        go.Scatter(
            x=monthly['mes_ano'],
            y=monthly['selic'],
            mode='lines+markers',
            name='Selic',
            line={'color': '#d62728'}
        ),
        secondary_y=True
    )
    figure.update_layout(
        height=520,
        hovermode='x unified',
        legend={'orientation': 'h', 'y': 1.1},
        margin={'l': 20, 'r': 20, 't': 30, 'b': 20}
    )
    figure.update_xaxes(title_text='Mês/Ano', type='category')
    figure.update_yaxes(title_text='Dólar (R$)', secondary_y=False)
    figure.update_yaxes(title_text='Selic', secondary_y=True)
    return figure

# --- INTERFACE DO USUÁRIO ---

st.title("🏦 DolarTracker – Análise de Cotação do Dólar e Selic (5 anos)")

# Carregar dados
df = fetch_data()
pivot_df = fetch_pivot_data()

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
    st.subheader("📈 Frequência mensal: Dólar e Selic")
    if not pivot_df.empty:
        st.plotly_chart(build_monthly_chart(pivot_df), use_container_width=True)

    st.subheader(f"📊 Dados diários: {tipo_selecionado.capitalize()}")
    # O Streamlit precisa que o index seja a data para o line_chart funcionar bem
    chart_data = df.set_index('data')[['valor']]
    st.line_chart(chart_data)

    # Tabela de dados
    with st.expander("🔍 Visualizar tabela de dados brutos"):
        st.dataframe(df, use_container_width=True)