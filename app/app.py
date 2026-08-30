import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sqlalchemy import text
from config.database import get_connection as database_connection


st.set_page_config(
    page_title="📊 DolarTracker",
    layout="wide"
)


# Mapeamento canônico do identificador interno (DB/ETL) para a etiqueta exibida.
TIPO_LABELS = {'dolar': 'Dólar', 'selic_meta': 'Selic Meta'}


def format_value(valor, is_dolar):
    """Formata `valor` como moeda (Dólar) ou porcentagem (Selic), vetorizado."""
    if pd.isna(valor):
        return ''
    return f"R$ {valor:,.2f}" if is_dolar else f"{valor:.2f}%"


_formatter = np.vectorize(format_value, otypes=[object])


def get_connection():
    return database_connection()


def fetch_data():
    """Carrega a série histórica a partir da view pivotada."""
    query = text("""
        SELECT data, dolar, selic_meta
        FROM cotacao_dolar_selic_pivot
        ORDER BY data;
    """)
    empty = pd.DataFrame(columns=['data', 'dolar', 'selic_meta'])
    try:
        with get_connection() as conn:
            df = pd.read_sql(query, conn)
    except Exception as e:
        st.error(f"Erro ao carregar a view: {e}")
        return empty

    if df.empty:
        return empty
    df['data'] = pd.to_datetime(df['data'])
    # A view expõe `numeric` como Decimal no psycopg; convertemos para float
    # para que Plotly e os formatadores de string operem diretamente.
    for col in ('dolar', 'selic_meta'):
        df[col] = pd.to_numeric(df[col], errors='coerce')
    return df


def compute_axis_settings(df_janela, granularity):
    """Calcula formato, dtick, tick0 e range do eixo X para a janela atual."""
    if df_janela.empty:
        now = pd.Timestamp.now()
        return '%d/%m', 24 * 60 * 60 * 1000, now, now, now

    span_days = max(
        (df_janela['data'].max() - df_janela['data'].min()).days,
        1
    )

    if granularity == 'semana':
        tick_format = '%d/%m'
        dtick = 24 * 60 * 60 * 1000
        tick0 = df_janela['data'].min()
    else:
        # 'mes' e 'acumulado' usam ticks mensais alinhados ao início do mês
        tick_format = '%m/%y'
        dtick = 'M1'
        tick0 = pd.Timestamp(
            year=df_janela['data'].min().year,
            month=df_janela['data'].min().month,
            day=1
        )

    pad = pd.Timedelta(days=max(round(span_days * 0.05), 1))

    return (
        tick_format,
        dtick,
        tick0,
        df_janela['data'].min() - pad,
        df_janela['data'].max() + pad
    )


def build_chart(df, granularity='mes'):
    """
    Constrói o gráfico Plotly de eixo duplo (Dólar à esquerda, Selic Meta à direita).

    Granularidades:
        semana:    últimos 7 dias, com pontos de mudança da Selic
        mes:       últimos 30 dias, com pontos de mudança da Selic
        acumulado: média mensal de todo o período
    """
    df_plot = df.copy().sort_values('data').set_index('data')

    if granularity not in {'semana', 'mes', 'acumulado'}:
        granularity = 'mes'

    if df_plot.empty:
        return None

    if granularity == 'acumulado':
        aggregated = (
            df_plot[['dolar', 'selic_meta']]
            .resample('M')
            .mean()
            .dropna(subset=['dolar', 'selic_meta'], how='all')
            .reset_index()
        )
        label = 'Acumulado mensal'
    else:
        janela_dias = {'semana': 7, 'mes': 30}[granularity]
        data_inicio_janela = df_plot.index.max() - pd.Timedelta(days=janela_dias - 1)
        df_janela = df_plot.loc[df_plot.index >= data_inicio_janela]
        if df_janela.empty:
            return None
        aggregated = df_janela[['dolar', 'selic_meta']].reset_index()
        label = 'Últimos 7 dias' if granularity == 'semana' else 'Últimos 30 dias'

    if aggregated.empty:
        return None

    aggregated['data_str'] = aggregated['data'].dt.strftime('%d/%m/%Y')

    if granularity == 'acumulado':
        dollar_trace = go.Scatter(
            x=aggregated['data'],
            y=aggregated['dolar'],
            mode='lines+markers+text',
            name='Dólar',
            connectgaps=True,
            line={'color': '#1f77b4', 'smoothing': 0.4},
            line_shape='spline',
            marker={'size': 6},
            text=aggregated['dolar'].map(
                lambda v: f'R$ {v:,.2f}' if pd.notna(v) else ''
            ),
            textposition='top center',
            textfont={'color': '#1f77b4', 'size': 10},
            hovertemplate=(
                '<b>Data:</b> %{customdata}'
                '<br><b>Dólar:</b> R$ %{y:,.2f}'
                '<extra></extra>'
            ),
            customdata=aggregated['data_str']
        )

        selic_trace = go.Scatter(
            x=aggregated['data'],
            y=aggregated['selic_meta'],
            mode='lines+markers+text',
            name='Selic Meta',
            connectgaps=True,
            line={'color': '#d62728', 'shape': 'hv'},
            marker={'size': 6},
            text=aggregated['selic_meta'].map(
                lambda v: f'{v:,.2f}%' if pd.notna(v) else ''
            ),
            textposition='bottom center',
            textfont={'color': '#d62728', 'size': 10},
            hovertemplate=(
                '<b>Data:</b> %{customdata}'
                '<br><b>Selic Meta:</b> %{y:.2f}%'
                '<extra></extra>'
            ),
            customdata=aggregated['data_str']
        )
    else:
        daily = (
            df_plot.loc[df_plot.index >= data_inicio_janela][['dolar', 'selic_meta']]
            .copy()
            .sort_index()
            .reset_index()
            .rename(columns={'index': 'data'})
        )
        daily['data_str'] = daily['data'].dt.strftime('%d/%m/%Y')

        # Mantém apenas os pontos em que a Selic Meta muda (mais primeiro e último),
        # evitando um degrau horizontal redundante em janelas curtas.
        daily['selic_prev'] = daily['selic_meta'].shift(1)
        selic_change = daily[
            (daily['selic_meta'] != daily['selic_prev'])
            | (daily.index == 0)
            | (daily.index == len(daily) - 1)
        ].copy()
        if selic_change.empty:
            selic_change = daily.iloc[[0, len(daily) - 1]].copy()
        selic_change = selic_change[['data', 'data_str', 'selic_meta']].copy()
        selic_change['value_label'] = selic_change['selic_meta'].map(
            lambda v: f'{v:,.2f}%'
        )

        dollar_trace = go.Scatter(
            x=daily['data'],
            y=daily['dolar'],
            mode='lines+markers+text',
            name='Dólar',
            connectgaps=True,
            line={'color': '#1f77b4', 'smoothing': 0.4},
            line_shape='spline',
            marker={'size': 6},
            text=daily['dolar'].map(
                lambda v: f'R$ {v:,.2f}' if pd.notna(v) else ''
            ),
            textposition='top center',
            textfont={'color': '#1f77b4', 'size': 10},
            hovertemplate=(
                '<b>Data:</b> %{customdata}'
                '<br><b>Dólar:</b> R$ %{y:,.2f}'
                '<extra></extra>'
            ),
            customdata=daily['data_str']
        )

        selic_trace = go.Scatter(
            x=selic_change['data'],
            y=selic_change['selic_meta'],
            mode='lines+markers+text',
            name='Selic Meta',
            connectgaps=True,
            line={'color': '#d62728', 'shape': 'hv'},
            marker={'size': 7},
            text=selic_change['value_label'],
            textposition='top center',
            textfont={'color': '#d62728', 'size': 10},
            hovertemplate=(
                '<b>Data:</b> %{customdata}'
                '<br><b>Selic Meta:</b> %{y:.2f}%'
                '<extra></extra>'
            ),
            customdata=selic_change['data_str']
        )

    figure = make_subplots(specs=[[{'secondary_y': True}]])
    figure.add_trace(dollar_trace, secondary_y=False)
    figure.add_trace(selic_trace, secondary_y=True)

    plot_height = 700 if granularity == 'acumulado' else 520

    figure.update_layout(
        height=plot_height,
        autosize=True,
        paper_bgcolor='#000000',
        plot_bgcolor='#000000',
        hovermode='x unified',
        legend={'orientation': 'h', 'y': 1.1},
        margin={'l': 20, 'r': 20, 't': 50, 'b': 80},
        # Mantém o estado de zoom/seleção entre re-renders do Streamlit
        uirevision='dolartracker'
    )

    tick_format, dtick, tick0, range_min, range_max = compute_axis_settings(
        aggregated, granularity
    )

    if granularity == 'acumulado':
        data_max = aggregated['data'].max()
        data_min = aggregated['data'].min()
        data_inicio_zoom = max(data_max - pd.DateOffset(months=12), data_min)
        figure.update_xaxes(
            title_text=f'Período ({label})',
            type='date',
            tickformat=tick_format,
            tickangle=0,
            dtick=dtick,
            tick0=tick0,
            automargin=True,
            range=[data_inicio_zoom, data_max],
            fixedrange=False,
            rangeslider={'visible': True, 'thickness': 0.015, 'borderwidth': 1}
        )
    else:
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


st.title("🏦 DolarTracker – Análise de Cotação do Dólar e Selic Meta (10 anos)")

pivot_df = fetch_data()
df = pivot_df.copy()

if df.empty:
    st.warning(
        "Nenhum dado encontrado na view cotacao_dolar_selic_pivot. "
        "Certifique-se de rodar o script de ETL primeiro."
    )
    st.stop()

# Deriva a forma long (uma linha por data+tipo) usada em métricas, estatísticas e tabela.
df_long = (
    df.melt(id_vars=['data'], var_name='tipo', value_name='valor')
    .dropna(subset=['valor'])
    .assign(
        data_dt=lambda d: pd.to_datetime(d['data'], errors='coerce'),
        tipo=lambda d: d['tipo'].str.lower().replace({
            'selic': 'selic_meta',
            'selic_meta': 'selic_meta'
        })
    )
    .dropna(subset=['data_dt'])
    .sort_values(['data_dt', 'tipo'], ascending=[False, True])
    .reset_index(drop=True)
)
df_long['data'] = df_long['data_dt'].dt.strftime('%d/%m/%Y')

col1, col2 = st.columns(2)

ultimo_dolar = df_long[df_long['tipo'] == 'dolar'].iloc[0]
ultimo_selic = df_long[df_long['tipo'] == 'selic_meta'].iloc[0]

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

st.subheader("📊 Resumo estatístico do dataset")

df_stats = df_long.copy()
df_stats['valor'] = pd.to_numeric(df_stats['valor'], errors='coerce')
df_stats = df_stats.dropna(subset=['valor'])

if not df_stats.empty:
    summary_by_type = (
        df_stats
        .groupby('tipo', as_index=False)['valor']
        .agg(
            registros='count',
            media='mean',
            minimo='min',
            Q1=lambda s: s.quantile(0.25),
            Mediana='median',
            Q3=lambda s: s.quantile(0.75),
            maximo='max',
            desvio_padrao='std'
        )
        .sort_values('tipo')
    )
    summary_by_type['tipo'] = summary_by_type['tipo'].map(TIPO_LABELS)
    is_dolar = (summary_by_type['tipo'] == 'Dólar').to_numpy()
    num_cols = ['media', 'minimo', 'Q1', 'Mediana', 'Q3', 'maximo', 'desvio_padrao']
    for col in num_cols:
        summary_by_type[col] = _formatter(summary_by_type[col].to_numpy(), is_dolar)
    st.dataframe(summary_by_type, use_container_width=True, hide_index=True)

st.subheader("📈 Frequência temporal: Dólar e Selic Meta")

granularity = st.selectbox(
    "Granularidade",
    ["semana", "mes", "acumulado"],
    index=1,
    format_func=lambda x: {
        'semana': 'Semana',
        'mes': 'Mês',
        'acumulado': 'Acumulado'
    }[x]
)

monthly_figure = build_chart(pivot_df, granularity=granularity)
if monthly_figure is not None:
    st.plotly_chart(
        monthly_figure,
        use_container_width=True,
        config={
            'responsive': True,
            'displayModeBar': False,
            'scrollZoom': False
        }
    )

with st.expander("🔍 Visualizar tabela de dados brutos"):
    df_raw = (
        df_long[['data', 'tipo', 'valor', 'data_dt']]
        .sort_values(['data_dt', 'tipo'], ascending=[False, True])
        .reset_index(drop=True)
    )
    df_raw['tipo'] = df_raw['tipo'].map(TIPO_LABELS)
    is_dolar = (df_raw['tipo'] == 'Dólar').to_numpy()
    df_raw['valor_formatado'] = _formatter(df_raw['valor'].to_numpy(), is_dolar)
    st.dataframe(
        df_raw[['data_dt', 'tipo', 'valor_formatado']],
        use_container_width=True,
        hide_index=True,
        column_config={
            'data_dt': st.column_config.DatetimeColumn('Data', format='DD/MM/YYYY'),
            'tipo': st.column_config.TextColumn('Tipo'),
            'valor_formatado': st.column_config.TextColumn('Valor')
        }
    )