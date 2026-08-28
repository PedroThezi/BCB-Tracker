import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from config.database import get_connection as database_connection

# Configuração da página (deve ser o primeiro comando Streamlit)
st.set_page_config(page_title="📊 DolarTracker", layout="wide")

def get_connection():
    return database_connection()


def fetch_data():
    """Busca os dados somente na view pivotada."""
    conn = None
    try:
        conn = get_connection()
        query = """
            SELECT data,
                   dolar,
                   CASE
                       WHEN selic_meta IS NOT NULL THEN selic_meta
                       ELSE selic
                   END AS selic_meta
            FROM cotacao_dolar_selic_pivot
            ORDER BY data;
        """
        try:
            df = pd.read_sql(query, conn)
        except Exception:
            # Compatibilidade com a view antiga, que ainda expõe somente `selic`.
            conn.rollback()
            df = pd.read_sql(
                """
                    SELECT data, dolar, selic AS selic_meta
                    FROM cotacao_dolar_selic_pivot
                    ORDER BY data;
                """,
                conn
            )

        if not df.empty:
            df['data'] = pd.to_datetime(df['data'])

        return df
    except Exception as e:
        st.error(f"Erro ao carregar a view: {e}")
        return pd.DataFrame(columns=['data', 'dolar', 'selic_meta'])
    finally:
        if conn is not None:
            conn.close()


def compute_axis_settings(df_janela, granularity):
    """Calcula tick_format, dtick e tick0 do eixo X de acordo com a janela
    filtrada (7, 30 ou 365 dias)."""
    span_days = max((df_janela['data'].max() - df_janela['data'].min()).days, 1)

    if granularity == 'semana':
        tick_format = '%d/%m'
        dtick = 24 * 60 * 60 * 1000  # 1 dia
        tick0 = df_janela['data'].min()
    elif granularity == 'ano':
        tick_format = '%m/%y'
        dtick = 'M1'
        tick0 = pd.Timestamp(year=df_janela['data'].min().year, month=df_janela['data'].min().month, day=1)
    else:  # mes
        tick_format = '%d/%m'
        step_days = max(1, round(span_days / 10))  # ~10 marcações para 30 dias
        dtick = step_days * 24 * 60 * 60 * 1000
        tick0 = df_janela['data'].min()

    pad = pd.Timedelta(days=max(round(span_days * 0.05), 1))
    return tick_format, dtick, tick0, df_janela['data'].min() - pad, df_janela['data'].max() + pad


def build_chart(df, granularity='mes'):
    """Cria o gráfico filtrado por janela temporal fixa:
    semana = últimos 7 dias (diário), mes = últimos 30 dias (diário),
    ano = últimos 365 dias (média mensal).
    """
    df_plot = df.copy().sort_values('data').set_index('data')

    if granularity not in {'semana', 'mes', 'ano'}:
        granularity = 'mes'

    if df_plot.empty:
        return None

    # A taxa permanece válida até a próxima atualização; preenche antes do
    # recorte para carregar também a última taxa publicada antes da janela.
    df_plot['selic_meta'] = df_plot['selic_meta'].ffill()

    data_max = df_plot.index.max()
    janela_dias = {'semana': 7, 'mes': 30, 'ano': 365}[granularity]
    data_inicio_janela = data_max - pd.Timedelta(days=janela_dias - 1)
    df_janela = df_plot.loc[df_plot.index >= data_inicio_janela]

    if df_janela.empty:
        return None

    df_janela = df_janela.copy()

    if granularity == 'ano':
        aggregated = (
            df_janela[['dolar', 'selic_meta']]
            .resample('M')
            .mean()
            .dropna(subset=['dolar', 'selic_meta'], how='all')
            .reset_index()
        )
        label = 'Últimos 12 meses'
    else:
        aggregated = df_janela[['dolar', 'selic_meta']].reset_index()
        label = 'Últimos 7 dias' if granularity == 'semana' else 'Últimos 30 dias'

    if aggregated.empty:
        return None

    figure = make_subplots(specs=[[{'secondary_y': True}]])
    figure.add_trace(
        go.Scatter(
            x=aggregated['data'],
            y=aggregated['dolar'],
            mode='lines+markers+text',
            name='Dólar',
            line={'color': '#1f77b4'},
            text=aggregated['dolar'].map(lambda v: f'R$ {v:,.2f}'),
            textposition='top center',
            textfont={'color': '#1f77b4', 'size': 10},
            hovertemplate='Dólar: R$ %{y:,.2f}<extra></extra>'
        ),
        secondary_y=False
    )
    figure.add_trace(
        go.Scatter(
            x=aggregated['data'],
            y=aggregated['selic_meta'],
            mode='lines+markers+text',
            name='Selic Meta',
            line={'color': '#d62728'},
            text=aggregated['selic_meta'].map(lambda v: f'{v:,.2f}%'),
            textposition='bottom center',
            textfont={'color': '#d62728', 'size': 10},
            hovertemplate='Selic Meta: %{y:.2f}%<extra></extra>'
        ),
        secondary_y=True
    )
    figure.update_layout(
        height=520,
        autosize=True,
        paper_bgcolor='#000000',
        plot_bgcolor='#000000',
        hovermode='x unified',
        legend={'orientation': 'h', 'y': 1.1},
        margin={'l': 20, 'r': 20, 't': 30, 'b': 20}
    )

    tick_format, dtick, tick0, range_min, range_max = compute_axis_settings(aggregated, granularity)

    figure.update_xaxes(
        title_text=f'Período ({label})',
        type='date',
        tickformat=tick_format,
        tickangle=0,
        dtick=dtick,
        tick0=tick0,
        automargin=True,
        range=[range_min, range_max],
        fixedrange=True
    )
    figure.update_yaxes(
        title_text='Dólar (R$)',
        title_font={'color': '#d1d5db'},
        fixedrange=True,
        secondary_y=False,
        automargin=True
    )
    figure.update_yaxes(
        title_text='Selic Meta (% a.a.)',
        title_font={'color': '#d1d5db'},
        ticksuffix='%',
        fixedrange=True,
        secondary_y=True,
        automargin=True
    )
    return figure

# --- INTERFACE DO USUÁRIO ---

st.title("🏦 DolarTracker – Análise de Cotação do Dólar e Selic Meta (5 anos)")

# Carregar dados somente da view
pivot_df = fetch_data()

df = pivot_df.copy()

if df.empty:
    st.warning("Nenhum dado encontrado na view cotacao_dolar_selic_pivot. Certifique-se de rodar o script de ETL primeiro.")
else:
    df_long = df.melt(id_vars=['data'], var_name='tipo', value_name='valor')
    df_long = df_long.dropna(subset=['valor']).sort_values('data', ascending=False).reset_index(drop=True)
    df_long['data_dt'] = pd.to_datetime(df_long['data']).dt.floor('D')
    df_long['data'] = df_long['data_dt'].dt.strftime('%d/%m/%Y')
    df_long['tipo'] = df_long['tipo'].str.lower()
    df_long['tipo'] = df_long['tipo'].replace({'selic': 'selic_meta', 'selic_meta': 'selic_meta'})

    # Layout de Colunas para métricas rápidas (Opcional - Dá um ar de BI Profissional)
    col1, col2 = st.columns(2)
    if not df_long.empty:
        ultimo_dolar = df_long[df_long['tipo'] == 'dolar'].sort_values('data_dt', ascending=False).iloc[0]
        ultimo_selic = df_long[df_long['tipo'] == 'selic_meta'].sort_values('data_dt', ascending=False).iloc[0]

        col1.metric(
            "Último registro - Dólar",
            f"R$ {ultimo_dolar['valor']:,.2f}",
            help=f"Data: {ultimo_dolar['data']}"
        )
        col2.metric(
            "Último registro - Selic Meta",
            f"{ultimo_selic['valor']:.2f}%",
            help=f"Data: {ultimo_selic['data']}"
        )

    if not df_long.empty:
        df_stats = df_long.copy()
        df_stats['valor'] = pd.to_numeric(df_stats['valor'], errors='coerce')
        df_stats = df_stats.dropna(subset=['valor'])

        if not df_stats.empty:
            summary = df_stats['valor'].agg(['count', 'mean', 'std', 'min', 'max'])
            st.subheader("📊 Resumo estatístico do dataset")
            summary_by_type = (
                df_stats.groupby('tipo', as_index=False)['valor']
                .agg(
                    registros='count',
                    media='mean',
                    minimo='min',
                    maximo='max',
                    desvio_padrao='std'
                )
                .sort_values('tipo')
            )

            summary_by_type['tipo'] = summary_by_type['tipo'].replace({'selic_meta': 'Selic Meta', 'dolar': 'Dólar'})

            summary_by_type['media'] = summary_by_type.apply(
                lambda row: (
                    f"R$ {row['media']:,.2f}" if row['tipo'] == 'Dólar' else f"{row['media']:.2f}%"
                ),
                axis=1
            )
            summary_by_type['minimo'] = summary_by_type.apply(
                lambda row: (
                    f"R$ {row['minimo']:,.2f}" if row['tipo'] == 'Dólar' else f"{row['minimo']:.2f}%"
                ),
                axis=1
            )
            summary_by_type['maximo'] = summary_by_type.apply(
                lambda row: (
                    f"R$ {row['maximo']:,.2f}" if row['tipo'] == 'Dólar' else f"{row['maximo']:.2f}%"
                ),
                axis=1
            )
            summary_by_type['desvio_padrao'] = summary_by_type.apply(
                lambda row: (
                    f"R$ {row['desvio_padrao']:,.2f}" if row['tipo'] == 'Dólar' else f"{row['desvio_padrao']:.2f}%"
                ),
                axis=1
            )
            st.dataframe(summary_by_type, use_container_width=True, hide_index=True)

    # Exibir gráfico
    st.subheader("📈 Frequência temporal: Dólar e Selic Meta")
    granularity = st.selectbox(
        "Granularidade",
        ["semana", "mes", "ano"],
        index=1,
        format_func=lambda x: {
            'semana': 'Semana',
            'mes': 'Mês',
            'ano': 'Ano'
        }[x]
    )

    if not pivot_df.empty:
        monthly_figure = build_chart(pivot_df, granularity=granularity)
        if monthly_figure is not None:
            st.plotly_chart(
                monthly_figure,
                use_container_width=True,
                config={'responsive': True, 'displayModeBar': False}
            )

    with st.expander("🔍 Visualizar tabela de dados brutos"):
        df_long = df_long.copy()
        df_long = df_long[['data', 'tipo', 'valor']].sort_values(['data', 'tipo'], ascending=[False, True]).reset_index(drop=True)
        st.dataframe(df_long, use_container_width=True)
