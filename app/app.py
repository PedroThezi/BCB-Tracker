import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from sqlalchemy import text
from config.database import get_connection as database_connection


# =============================================================
# CONFIGURAÇÃO DA PÁGINA
# =============================================================

st.set_page_config(
    page_title="📊 DolarTracker",
    layout="wide"
)


def get_connection():
    return database_connection()


# =============================================================
# BUSCAR DADOS
# =============================================================

def fetch_data():
    """Busca os dados somente na view pivotada."""

    conn = None

    try:
        conn = get_connection()

        query = """
            SELECT data, dolar, selic_meta
            FROM cotacao_dolar_selic_pivot
            ORDER BY data;
        """

        df = pd.read_sql(text(query), conn)

        if not df.empty:
            df['data'] = pd.to_datetime(df['data'])

        return df

    except Exception as e:

        st.error(
            f"Erro ao carregar a view: {e}"
        )

        return pd.DataFrame(
            columns=[
                'data',
                'dolar',
                'selic_meta'
            ]
        )

    finally:

        if conn is not None:
            conn.close()


# =============================================================
# CONFIGURAÇÕES DO EIXO X
# =============================================================

def compute_axis_settings(
    df_janela,
    granularity
):
    """
    Calcula tick_format, dtick e tick0
    de acordo com a janela filtrada.
    """

    if df_janela.empty:

        return (
            '%d/%m',
            24 * 60 * 60 * 1000,
            pd.Timestamp.now(),
            pd.Timestamp.now(),
            pd.Timestamp.now()
        )

    span_days = max(
        (
            df_janela['data'].max()
            - df_janela['data'].min()
        ).days,
        1
    )

    if granularity == 'semana':

        tick_format = '%d/%m'

        dtick = (
            24
            * 60
            * 60
            * 1000
        )

        tick0 = df_janela['data'].min()

    elif granularity == 'acumulado':

        tick_format = '%m/%y'

        dtick = 'M1'

        tick0 = pd.Timestamp(
            year=df_janela['data'].min().year,
            month=df_janela['data'].min().month,
            day=1
        )


    else:  # mes

        tick_format = '%m/%y'

        dtick = 'M1'

        tick0 = pd.Timestamp(
            year=df_janela['data'].min().year,
            month=df_janela['data'].min().month,
            day=1
        )

    pad = pd.Timedelta(
        days=max(
            round(span_days * 0.05),
            1
        )
    )

    return (
        tick_format,
        dtick,
        tick0,
        df_janela['data'].min() - pad,
        df_janela['data'].max() + pad
    )


# =============================================================
# CONSTRUÇÃO DO GRÁFICO
# =============================================================

def build_chart(
    df,
    granularity='mes'
):
    """
    Cria o gráfico conforme a granularidade:

    semana:
        últimos 7 dias

    mes:
        últimos 30 dias


    acumulado:
        média mensal de todo o período

    Os pontos existentes são mantidos.
    Quando houver dados ausentes entre dois pontos,
    o Plotly conecta os pontos reais através de connectgaps=True.
    """

    df_plot = (
        df.copy()
        .sort_values('data')
        .set_index('data')
    )

    valid_granularities = {
        'semana',
        'mes',
        'acumulado'
    }

    if granularity not in valid_granularities:

        granularity = 'mes'

    if df_plot.empty:
        return None

    # =========================================================
    # ACUMULADO
    # =========================================================

    if granularity == 'acumulado':

        aggregated = (
            df_plot[
                [
                    'dolar',
                    'selic_meta'
                ]
            ]
            .resample('M')
            .mean()
            .dropna(
                subset=[
                    'dolar',
                    'selic_meta'
                ],
                how='all'
            )
            .reset_index()
        )

        label = 'Acumulado mensal'

    # =========================================================
    # SEMANA / MÊS
    # =========================================================

    else:

        data_max = df_plot.index.max()

        janela_dias = {
            'semana': 7,
            'mes': 30,
        }[granularity]

        data_inicio_janela = (
            data_max
            - pd.Timedelta(
                days=janela_dias - 1
            )
        )

        df_janela = df_plot.loc[
            df_plot.index >= data_inicio_janela
        ]

        if df_janela.empty:
            return None

        aggregated = (
            df_janela[
                [
                    'dolar',
                    'selic_meta'
                ]
            ]
            .reset_index()
        )

        label = (
            'Últimos 7 dias'
            if granularity == 'semana'
            else 'Últimos 30 dias'
            if granularity == 'mes'
            else 'Últimos 365 dias'
        )

    if aggregated.empty:
        return None

    # =========================================================
    # DATA FORMATADA
    # =========================================================

    aggregated['data_str'] = (
        aggregated['data']
        .dt.strftime('%d/%m/%Y')
    )

    # =========================================================
    # GRÁFICO ACUMULADO
    # =========================================================

    if granularity == 'acumulado':

        # -----------------------------------------------------
        # DÓLAR
        # -----------------------------------------------------

        dollar_trace = go.Scatter(

            x=aggregated['data'],

            y=aggregated['dolar'],

            mode='lines+markers+text',

            name='Dólar',

            connectgaps=True,

            line={
                'color': '#1f77b4',
                'smoothing': 0.4
            },

            line_shape='spline',

            marker={
                'size': 6
            },

            text=aggregated['dolar'].map(
                lambda v:
                f'R$ {v:,.2f}'
                if pd.notna(v)
                else ''
            ),

            textposition='top center',

            textfont={
                'color': '#1f77b4',
                'size': 10
            },

            hovertemplate=(
                '<b>Data:</b> %{customdata}'
                '<br>'
                '<b>Dólar:</b> R$ %{y:,.2f}'
                '<extra></extra>'
            ),

            customdata=aggregated['data_str']
        )

        # -----------------------------------------------------
        # SELIC
        # -----------------------------------------------------

        selic_trace = go.Scatter(

            x=aggregated['data'],

            y=aggregated['selic_meta'],

            mode='lines+markers+text',

            name='Selic Meta',

            connectgaps=True,

            line={
                'color': '#d62728',
                'shape': 'hv'
            },

            marker={
                'size': 6
            },

            text=aggregated['selic_meta'].map(
                lambda v:
                f'{v:,.2f}%'
                if pd.notna(v)
                else ''
            ),

            textposition='bottom center',

            textfont={
                'color': '#d62728',
                'size': 10
            },

            hovertemplate=(
                '<b>Data:</b> %{customdata}'
                '<br>'
                '<b>Selic Meta:</b> %{y:.2f}%'
                '<extra></extra>'
            ),

            customdata=aggregated['data_str']
        )

    # =========================================================
    # GRÁFICO SEMANA / MÊS
    # =========================================================

    else:

        df_janela = df_plot.loc[
            df_plot.index >= data_inicio_janela
        ].copy()

        daily = (
            df_janela[
                [
                    'dolar',
                    'selic_meta'
                ]
            ]
            .copy()
            .sort_index()
        )

        daily = (
            daily
            .reset_index()
            .rename(
                columns={
                    'index': 'data'
                }
            )
        )

        daily['data_str'] = (
            daily['data']
            .dt.strftime('%d/%m/%Y')
        )

        # -----------------------------------------------------
        # IDENTIFICA ALTERAÇÕES DA SELIC
        # -----------------------------------------------------

        daily['selic_prev'] = (
            daily['selic_meta'].shift(1)
        )

        selic_change = daily[
            (
                daily['selic_meta']
                != daily['selic_prev']
            )
            |
            (daily.index == 0)
            |
            (
                daily.index
                == len(daily) - 1
            )
        ].copy()

        if selic_change.empty:

            selic_change = daily.iloc[
                [
                    0,
                    len(daily) - 1
                ]
            ].copy()

        selic_change = selic_change[
            [
                'data',
                'data_str',
                'selic_meta'
            ]
        ].copy()

        selic_change['value_label'] = (
            selic_change['selic_meta']
            .map(
                lambda v:
                f'{v:,.2f}%'
            )
        )

        # -----------------------------------------------------
        # DÓLAR
        # -----------------------------------------------------

        dollar_trace = go.Scatter(

            x=daily['data'],

            y=daily['dolar'],

            mode='lines+markers+text',

            name='Dólar',

            # Apenas conecta os pontos reais.
            # Não cria novos pontos.
            connectgaps=True,

            line={
                'color': '#1f77b4',
                'smoothing': 0.4
            },

            line_shape='spline',

            marker={
                'size': 6
            },

            text=daily['dolar'].map(
                lambda v:
                f'R$ {v:,.2f}'
                if pd.notna(v)
                else ''
            ),

            textposition='top center',

            textfont={
                'color': '#1f77b4',
                'size': 10
            },

            hovertemplate=(
                '<b>Data:</b> %{customdata}'
                '<br>'
                '<b>Dólar:</b> R$ %{y:,.2f}'
                '<extra></extra>'
            ),

            customdata=daily['data_str']
        )

        # -----------------------------------------------------
        # SELIC
        # -----------------------------------------------------

        selic_trace = go.Scatter(

            x=selic_change['data'],

            y=selic_change['selic_meta'],

            mode='lines+markers+text',

            name='Selic Meta',

            connectgaps=True,

            line={
                'color': '#d62728',
                'shape': 'hv'
            },

            marker={
                'size': 7
            },

            text=selic_change['value_label'],

            textposition='top center',

            textfont={
                'color': '#d62728',
                'size': 10
            },

            hovertemplate=(
                '<b>Data:</b> %{customdata}'
                '<br>'
                '<b>Selic Meta:</b> %{y:.2f}%'
                '<extra></extra>'
            ),

            customdata=selic_change['data_str']
        )

    # =========================================================
    # CRIA FIGURA
    # =========================================================

    figure = make_subplots(
        specs=[
            [
                {
                    'secondary_y': True
                }
            ]
        ]
    )

    figure.add_trace(
        dollar_trace,
        secondary_y=False
    )

    figure.add_trace(
        selic_trace,
        secondary_y=True
    )

    # =========================================================
    # ALTURA
    # =========================================================

    plot_height = (
        700
        if granularity == 'acumulado'
        else 520
    )

    # =========================================================
    # LAYOUT
    # =========================================================

    figure.update_layout(

        height=plot_height,

        autosize=True,

        paper_bgcolor='#000000',

        plot_bgcolor='#000000',

        hovermode='x unified',

        legend={
            'orientation': 'h',
            'y': 1.1
        },

        margin={
            'l': 20,
            'r': 20,
            't': 50,
            'b': 80
        },

        # Mantém o zoom enquanto o usuário interage
        uirevision='dolartracker'
    )

    # =========================================================
    # EIXO X
    # =========================================================

    (
        tick_format,
        dtick,
        tick0,
        range_min,
        range_max
    ) = compute_axis_settings(
        aggregated,
        granularity
    )

    # =========================================================
    # ACUMULADO: range slider + scroll horizontal
    # =========================================================

    if granularity == 'acumulado':

        data_max = aggregated['data'].max()
        data_min = aggregated['data'].min()

        data_inicio_zoom = data_max - pd.DateOffset(months=12)

        if data_inicio_zoom < data_min:
            data_inicio_zoom = data_min

        figure.update_xaxes(
        title_text=f'Período ({label})',
        type='date',
        tickformat=tick_format,
        tickangle=0,
        dtick=dtick,
        tick0=tick0,
        automargin=True,

        # Pequeno espaço antes e depois dos dados
        range=[
            data_inicio_zoom,
            data_max
        ],

        fixedrange=False,

        rangeslider={
            'visible': True,
            'thickness': 0.015,
            'borderwidth': 1
        }
    )

    # =========================================================
    # SEMANA / MÊS: zoom fixo (sem scroll)
    # =========================================================

    else:

        figure.update_xaxes(

            title_text=(
                f'Período ({label})'
            ),

            type='date',

            tickformat=tick_format,

            tickangle=0,

            dtick=dtick,

            tick0=tick0,

            automargin=True,

            range=[
                range_min,
                range_max
            ],

            fixedrange=True
        )

    # =========================================================
    # EIXO Y - DÓLAR
    # =========================================================

    figure.update_yaxes(

        title_text='Dólar (R$)',

        title_font={
            'color': '#d1d5db'
        },

        fixedrange=True,

        secondary_y=False,

        automargin=True
    )

    # =========================================================
    # EIXO Y - SELIC
    # =========================================================

    figure.update_yaxes(

        title_text='Selic Meta (% a.a.)',

        title_font={
            'color': '#d1d5db'
        },

        ticksuffix='%',

        fixedrange=True,

        secondary_y=True,

        automargin=True
    )

    return figure


# =============================================================
# INTERFACE DO USUÁRIO
# =============================================================

st.title(
    "🏦 DolarTracker – Análise de Cotação do Dólar e Selic Meta (10 anos)"
)


# =============================================================
# CARREGAR DADOS
# =============================================================

pivot_df = fetch_data()

df = pivot_df.copy()


if df.empty:

    st.warning(
        "Nenhum dado encontrado na view "
        "cotacao_dolar_selic_pivot. "
        "Certifique-se de rodar o script de ETL primeiro."
    )

else:

    # =========================================================
    # TRANSFORMAÇÃO DOS DADOS
    # =========================================================

    df_long = df.melt(
        id_vars=['data'],
        var_name='tipo',
        value_name='valor'
    )

    df_long = (
        df_long
        .dropna(
            subset=['valor']
        )
        .copy()
    )

    df_long['data_dt'] = pd.to_datetime(
        df_long['data'],
        errors='coerce'
    )

    df_long = (
        df_long
        .dropna(
            subset=['data_dt']
        )
        .sort_values(
            [
                'data_dt',
                'tipo'
            ],
            ascending=[
                False,
                True
            ]
        )
        .reset_index(drop=True)
    )

    df_long['data'] = (
        df_long['data_dt']
        .dt.strftime('%d/%m/%Y')
    )

    df_long['tipo'] = (
        df_long['tipo']
        .str.lower()
    )

    df_long['tipo'] = (
        df_long['tipo']
        .replace({
            'selic': 'selic_meta',
            'selic_meta': 'selic_meta'
        })
    )

    # =========================================================
    # MÉTRICAS
    # =========================================================

    col1, col2 = st.columns(2)

    if not df_long.empty:

        ultimo_dolar = (
            df_long[
                df_long['tipo'] == 'dolar'
            ]
            .sort_values(
                'data_dt',
                ascending=False
            )
            .iloc[0]
        )

        ultimo_selic = (
            df_long[
                df_long['tipo'] == 'selic_meta'
            ]
            .sort_values(
                'data_dt',
                ascending=False
            )
            .iloc[0]
        )

        col1.metric(

            "Último registro - Dólar",

            f"R$ {ultimo_dolar['valor']:,.2f}",

            help=(
                f"Data: "
                f"{ultimo_dolar['data']}"
            )
        )

        col2.metric(

            "Último registro - Selic Meta",

            f"{ultimo_selic['valor']:.2f}%",

            help=(
                f"Data: "
                f"{ultimo_selic['data']}"
            )
        )

    # =========================================================
    # RESUMO ESTATÍSTICO
    # =========================================================

    if not df_long.empty:

        df_stats = df_long.copy()

        df_stats['valor'] = pd.to_numeric(
            df_stats['valor'],
            errors='coerce'
        )

        df_stats = (
            df_stats
            .dropna(
                subset=['valor']
            )
        )

        if not df_stats.empty:

            st.subheader(
                "📊 Resumo estatístico do dataset"
            )

            def format_stat_value(
                value,
                tipo
            ):

                if tipo == 'Dólar':

                    return (
                        f"R$ {value:,.2f}"
                    )

                return (
                    f"{value:.2f}%"
                )

            summary_by_type = (

                df_stats

                .groupby(
                    'tipo',
                    as_index=False
                )['valor']

                .agg(

                    registros='count',

                    media='mean',

                    minimo='min',

                    quartil_1=lambda s:
                        s.quantile(0.25),

                    mediana='median',

                    quartil_3=lambda s:
                        s.quantile(0.75),

                    maximo='max',

                    desvio_padrao='std'
                )

                .sort_values('tipo')
            )

            summary_by_type['tipo'] = (
                summary_by_type['tipo']
                .replace({
                    'selic_meta': 'Selic Meta',
                    'dolar': 'Dólar'
                })
            )

            for column in [

                'media',
                'minimo',
                'quartil_1',
                'mediana',
                'quartil_3',
                'maximo',
                'desvio_padrao'

            ]:

                summary_by_type[column] = (

                    summary_by_type

                    .apply(

                        lambda row,
                        col=column:

                        format_stat_value(
                            row[col],
                            row['tipo']
                        ),

                        axis=1
                    )
                )

            summary_by_type = (
                summary_by_type
                .rename(
                    columns={
                        'quartil_1': 'Q1',
                        'mediana': 'Mediana',
                        'quartil_3': 'Q3'
                    }
                )
            )

            st.dataframe(

                summary_by_type,

                use_container_width=True,

                hide_index=True
            )

    # =========================================================
    # GRÁFICO
    # =========================================================

    st.subheader(
        "📈 Frequência temporal: Dólar e Selic Meta"
    )

    granularity = st.selectbox(

        "Granularidade",

        [
            "semana",
            "mes",
            "acumulado"
        ],

        index=1,

        format_func=lambda x: {

            'semana': 'Semana',

            'mes': 'Mês',

            'acumulado': 'Acumulado'

        }[x]
    )

    if not pivot_df.empty:

        monthly_figure = build_chart(

            pivot_df,

            granularity=granularity
        )

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

    # =========================================================
    # TABELA DE DADOS BRUTOS
    # =========================================================

    with st.expander(
        "🔍 Visualizar tabela de dados brutos"
    ):

        df_raw = df_long[
            [
                'data',
                'tipo',
                'valor',
                'data_dt'
            ]
        ].copy()

        df_raw = (
            df_raw
            .sort_values(
                [
                    'data_dt',
                    'tipo'
                ],
                ascending=[
                    False,
                    True
                ]
            )
            .reset_index(drop=True)
        )

        df_raw['tipo'] = (
            df_raw['tipo']
            .replace({
                'selic_meta': 'Selic Meta',
                'dolar': 'Dólar'
            })
        )

        df_raw['valor_formatado'] = (

            df_raw.apply(

                lambda row: (

                    f"R$ {row['valor']:,.2f}"

                    if row['tipo'] == 'Dólar'

                    else
                    f"{row['valor']:.2f}%"
                ),

                axis=1
            )
        )

        st.dataframe(

            df_raw[
                [
                    'data_dt',
                    'tipo',
                    'valor_formatado'
                ]
            ],

            use_container_width=True,

            hide_index=True,

            column_config={

                'data_dt':
                    st.column_config.DatetimeColumn(
                        'Data',
                        format='DD/MM/YYYY'
                    ),

                'tipo':
                    st.column_config.TextColumn(
                        'Tipo'
                    ),

                'valor_formatado':
                    st.column_config.TextColumn(
                        'Valor'
                    )
            }
        )