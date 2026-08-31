"""Shell do dashboard.

Configura a página, injeta o CSS e orquestra a composição. Toda a lógica
de UI e de dados mora em `app.views` e `app.data`.
"""
import streamlit as st

from app.data import build_long_df, fetch_data
from app.views import (
    GRANULARITY_LABELS,
    GRANULARITY_OPTIONS,
    inject_css,
    render_charts,
    render_header,
    render_overview,
    render_raw_data,
    render_summary,
    show_error,
)


st.set_page_config(
    page_title="BCB Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
    menu_items={"Get help": None, "Report a bug": None, "About": None},
)


def main():
    inject_css()

    pivot_df, fetch_error = fetch_data()
    if fetch_error:
        show_error(fetch_error)
        st.stop()
    if pivot_df.empty:
        show_error(
            "Nenhum dado encontrado na view cotacao_dolar_selic_pivot. "
            "Certifique-se de rodar o script de ETL primeiro.",
            level="warn",
        )
        st.stop()

    df_long = build_long_df(pivot_df)

    render_header(df_long)

    st.markdown('<p class="section-title">Visão geral</p>', unsafe_allow_html=True)
    render_overview(pivot_df)

    st.markdown('<p class="section-title">Frequência temporal</p>', unsafe_allow_html=True)
    granularity = st.segmented_control(
        "Granularidade",
        options=GRANULARITY_OPTIONS,
        default="mes",
        format_func=lambda x: GRANULARITY_LABELS[x],
        label_visibility="collapsed",
    )
    render_charts(pivot_df, granularity)

    st.markdown('<p class="section-title">Resumo estatístico</p>', unsafe_allow_html=True)
    render_summary(df_long)

    with st.expander("Ver dados brutos"):
        render_raw_data(df_long)


main()
