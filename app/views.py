"""Camada de apresentação do dashboard.

Tokens, formatadores, gráficos Plotly e renderers de cada seção da página.
Não acessa o banco — recebe DataFrames prontos.
"""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app.data import NUMERIC_COLUMNS


# ============================================================================
# Design tokens
# ============================================================================
# Single source of truth for colors, also referenced from the CSS block in
# `app.py` (via the `--token` custom properties).
TOKENS = {
    "page":   "#fafaf9",
    "card":   "#ffffff",
    "border": "#e7e5e4",
    "grid":   "#f1f0ed",
    "axis":   "#d6d3d1",
    "ink":    "#0a0a0a",
    "ink_2":  "#57534e",
    "ink_3":  "#78716c",
    "dolar":  "#2563eb",
    "selic":  "#ea580c",
    "font":   'system-ui, -apple-system, "Segoe UI", "Inter", sans-serif',
}


# ============================================================================
# Constants
# ============================================================================
TIPO_LABELS = {"dolar": "Dólar", "selic_meta": "Selic Meta"}

# Granularities exposed in the segmented control.
GRANULARITY_OPTIONS = ["semana", "mes", "acumulado"]
GRANULARITY_LABELS = {"semana": "Semana", "mes": "Mês", "acumulado": "Acumulado"}
WINDOW_DAYS = {"semana": 7, "mes": 30}

# Estatísticas calculadas para a tabela de resumo.
STATS_AGG = {
    "registros":     "count",
    "media":         "mean",
    "minimo":        "min",
    "Q1":            lambda s: s.quantile(0.25),
    "Mediana":       "median",
    "Q3":            lambda s: s.quantile(0.75),
    "maximo":        "max",
    "desvio_padrao": "std",
}
STATS_DISPLAY = ["media", "minimo", "Q1", "Mediana", "Q3", "maximo", "desvio_padrao"]

# Plotly defaults reaproveitando os tokens.
PLOTLY_DEFAULTS = dict(
    line_width=2,
    marker_size=6,
    font=dict(family=TOKENS["font"], color=TOKENS["ink_2"], size=12),
    hover_font=dict(family=TOKENS["font"], color=TOKENS["ink"], size=13),
)


# ============================================================================
# Formatting helpers
# ============================================================================
def _format_value(valor, is_dolar):
    """Formata `valor` como moeda (R$) ou porcentagem."""
    if pd.isna(valor):
        return ""
    return f"R$ {valor:,.2f}" if is_dolar else f"{valor:.2f}%"


def _format_value_series(series, is_dolar_array):
    """Vetoriza `_format_value` sobre uma Series, usando flags por linha."""
    return [
        _format_value(v, bool(flag))
        for v, flag in zip(series.to_numpy(), np.asarray(is_dolar_array))
    ]


def _variation_icon(pct):
    """Ícone (▲/▼/—) que representa a direção da variação `pct`."""
    if pct is None or pd.isna(pct) or abs(pct) < 0.005:
        return "—"
    return "▲" if pct > 0 else "▼"


def _variation_label(pct):
    """'ícone 0,30%' formatado; '—' quando a variação é desprezível."""
    icon = _variation_icon(pct)
    if icon == "—":
        return "—"
    return f"{icon} {abs(pct):.2f}%"


def _variation_labels(values):
    """Vetoriza `_variation_label` sobre uma Series/array."""
    return [_variation_label(v) for v in values]


def _ultimo_nao_nulo(series):
    """Último valor não-nulo de uma Series, ou NaN se todos forem nulos."""
    valid = series.dropna()
    return valid.iloc[-1] if not valid.empty else np.nan


# ============================================================================
# Chart helpers
# ============================================================================
def _window_or_resample(df_plot, granularity):
    """Aplica a janela (semana/mês) ou o resample mensal (acumulado).

    Preserva `dolar_variacao` / `selic_meta_variacao` para os tooltips.
    """
    cols = NUMERIC_COLUMNS
    if granularity == "acumulado":
        grouped = df_plot[cols].resample("M")
        aggregated = grouped.mean()
        # A variação é a última observação não-nula do mês (não uma média).
        last_var = grouped.agg(lambda s: s.dropna().iloc[-1] if s.dropna().size else np.nan)
        aggregated["dolar_variacao"] = last_var["dolar_variacao"]
        aggregated["selic_meta_variacao"] = last_var["selic_meta_variacao"]
        aggregated = (
            aggregated.dropna(subset=["dolar", "selic_meta"], how="all")
            .reset_index()
        )
        label = "Acumulado mensal (média por mês)"
        return aggregated, label

    janela_dias = WINDOW_DAYS[granularity]
    data_max = df_plot.index.max()
    data_inicio = data_max - pd.Timedelta(days=janela_dias - 1)
    df_janela = df_plot.loc[df_plot.index >= data_inicio]
    if df_janela.empty:
        return pd.DataFrame(), None
    aggregated = df_janela[cols].reset_index()
    label = "Últimos 7 dias" if granularity == "semana" else "Últimos 30 dias"
    return aggregated, label


def _selic_change_points(daily):
    """Seleciona os pontos em que a Selic muda (para o gráfico em degrau)."""
    daily = daily.copy()
    daily["selic_prev"] = daily["selic_meta"].shift(1)
    selic_change = daily[
        (daily["selic_meta"] != daily["selic_prev"])
        | (daily.index == 0)
        | (daily.index == len(daily) - 1)
    ].copy()
    if selic_change.empty:
        selic_change = daily.iloc[[0, len(daily) - 1]].copy()
    return selic_change[["data", "selic_meta"]].copy()


def _common_layout(fig, title, y_title, y_suffix=""):
    """Layout, eixos e tipografia compartilhados por ambas as séries."""
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color=TOKENS["ink"]), x=0.01, xanchor="left"),
        paper_bgcolor=TOKENS["card"],
        plot_bgcolor=TOKENS["card"],
        margin=dict(l=4, r=4, t=48, b=4),
        showlegend=False,
        height=340,
        font=PLOTLY_DEFAULTS["font"],
        hoverlabel=dict(
            bgcolor=TOKENS["card"], bordercolor=TOKENS["axis"],
            font=PLOTLY_DEFAULTS["hover_font"],
        ),
        hovermode="x",
    )
    fig.update_xaxes(
        type="date",
        showgrid=True, gridcolor=TOKENS["grid"], gridwidth=1,
        showline=True, linecolor=TOKENS["axis"], linewidth=1,
        ticks="outside", tickcolor=TOKENS["axis"], ticklen=4,
        tickfont=dict(color=TOKENS["ink_3"], size=11),
    )
    fig.update_yaxes(
        title=dict(text=y_title, font=dict(size=12, color=TOKENS["ink_3"])),
        showgrid=True, gridcolor=TOKENS["grid"], gridwidth=1,
        zeroline=False, showline=False,
        tickfont=dict(color=TOKENS["ink_3"], size=11),
        ticksuffix=y_suffix,
        rangemode="tozero" if y_suffix == "%" else "normal",
    )
    return fig


def _label_points(y_values, value_format, variation_pct):
    """Constrói o array de rótulos mostrado em apenas quatro pontos-chave
    (primeiro, último, máximo e mínimo). Os demais pontos ficam sem rótulo.

    O último ponto recebe também a variação % vs. ponto anterior, em uma
    segunda linha (formato `valor\\n{variação}`).
    """
    y = np.asarray(y_values, dtype=float)
    n = len(y)
    labels = [""] * n
    if n == 0:
        return labels
    valid = ~np.isnan(y)
    if not valid.any():
        return labels
    idx_first = int(np.where(valid)[0][0])
    idx_last = int(np.where(valid)[0][-1])
    idx_max = int(np.nanargmax(y))
    idx_min = int(np.nanargmin(y))

    var_last = "—"
    if idx_last > 0 and not pd.isna(variation_pct[idx_last]):
        var_last = _variation_label(variation_pct[idx_last])

    for i in {idx_first, idx_last, idx_max, idx_min}:
        labels[i] = value_format(y[i])
    # Acrescenta a variação como segunda linha do último rótulo.
    labels[idx_last] = f"{labels[idx_last]}\n{var_last}"
    return labels


def _build_chart(aggregated, granularity, *, column, color, line_shape, name,
                 y_title, y_suffix, value_format):
    """Constrói um gráfico Plotly (linha + marcadores) com variação no hover."""
    # No modo 'acumulado' plotamos todos os pontos; em 'semana'/'mês' (apenas
    # Selic) deduplicamos valores consecutivos para a linha em degrau.
    if column == "selic_meta" and granularity != "acumulado":
        plot_df = _selic_change_points(aggregated[["data", "selic_meta"]])
    else:
        plot_df = aggregated[["data", column]].copy()

    var_col = f"{column}_variacao"
    var_pct = plot_df["data"].map(dict(zip(aggregated["data"], aggregated[var_col])))
    customdata = np.column_stack([var_pct, _variation_labels(var_pct)])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=plot_df["data"],
        y=plot_df[column],
        mode="lines+markers",
        name=name,
        line=dict(color=color, width=PLOTLY_DEFAULTS["line_width"], shape=line_shape),
        marker=dict(size=PLOTLY_DEFAULTS["marker_size"], color=color,
                    line=dict(color=TOKENS["card"], width=1)),
        connectgaps=True,
        customdata=customdata,
        hovertemplate=(
            f"<b>%{{x|%d/%m/%Y}}</b>"
            f"<br>{value_format}"
            "<br>%{customdata[1]}"
            "<extra></extra>"
        ),
    ))

    # Rótulos de dados: apenas nos pontos-chave. A variação vai como segunda
    # linha apenas no último ponto (formato `valor\\n{variação}`).
    value_label = value_format.replace("%{y:,.2f}", "{:,.2f}").replace("%{y:.2f}", "{:.2f}")
    label_format_fn = lambda v: value_label.format(v)  # noqa: E731
    labels = _label_points(plot_df[column].to_numpy(), label_format_fn, var_pct.to_numpy())
    fig.add_trace(go.Scatter(
        x=plot_df["data"],
        y=plot_df[column],
        mode="text",
        text=labels,
        textposition="top center",
        textfont=dict(color=color, size=12, family=TOKENS["font"]),
        hoverinfo="skip",
        showlegend=False,
        cliponaxis=False,
    ))

    return _common_layout(fig, name, y_title, y_suffix=y_suffix)


def build_chart_dolar(aggregated, granularity):
    return _build_chart(
        aggregated, granularity,
        column="dolar", color=TOKENS["dolar"],
        line_shape="spline", name="Dólar Comercial",
        y_title="Cotação (R$)", y_suffix="",
        value_format="R$ %{y:,.2f}",
    )


def build_chart_selic(aggregated, granularity):
    return _build_chart(
        aggregated, granularity,
        column="selic_meta", color=TOKENS["selic"],
        line_shape="hv", name="Selic Meta",
        y_title="Taxa (% a.a.)", y_suffix="%",
        value_format="%{y:.2f}%",
    )


# ============================================================================
# Renderers
# ============================================================================
def show_error(message, *, level="error"):
    """Banner de erro ou aviso renderizado acima da página."""
    cls = "error" if level == "error" else "warn"
    st.markdown(f'<div class="notice {cls}">{message}</div>', unsafe_allow_html=True)


def inject_css():
    """Injeta o CSS global da página (chamado uma vez no boot)."""
    t = TOKENS
    st.markdown(
        f"""
<style>
  :root {{
    --surface-page: {t['page']};
    --surface-card: {t['card']};
    --border-hair:  {t['border']};
    --grid-hair:    {t['grid']};
    --axis-hair:    {t['axis']};
    --ink-primary:  {t['ink']};
    --ink-secondary:{t['ink_2']};
    --ink-muted:    {t['ink_3']};
    --accent-dolar: {t['dolar']};
    --accent-selic: {t['selic']};
    --delta-up:     #0a8a3a;
    --delta-down:   #b91c1c;
    --delta-neutral:{t['ink_3']};
    --err-bg:       #fef2f2;
    --err-border:   #fecaca;
    --err-ink:      #991b1b;
    --warn-bg:      #fffbeb;
    --warn-border:  #fde68a;
    --warn-ink:     #92400e;
    --font:         {t['font']};
  }}

  /* Page */
  html, body, [data-testid="stAppViewContainer"], .main, .block-container {{
    background: var(--surface-page) !important;
    color: var(--ink-primary) !important;
    font-family: var(--font) !important;
  }}
  .block-container {{ padding: 2.5rem 2.5rem 0; max-width: 1500px; }}
  #MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; height: 0; }}
  .modebar-container {{ display: none !important; }}

  /* Header */
  .app-header {{ padding: 0 0 1.75rem 0; border-bottom: 1px solid var(--border-hair); margin-bottom: 1.5rem; }}
  .app-header h1 {{
    font-size: 32px; font-weight: 700; letter-spacing: -0.02em;
    color: var(--ink-primary); margin: 0 0 0.35rem 0;
  }}
  .app-header .subtitle {{ color: var(--ink-secondary); font-size: 15px; margin: 0; }}
  .app-header .period {{ color: var(--ink-muted); font-size: 13px; margin: 0.5rem 0 0 0; }}

  /* Section title */
  .section-title {{
    font-size: 20px; font-weight: 600; color: var(--ink-primary);
    margin: 2rem 0 0.75rem 0; letter-spacing: -0.01em;
  }}

  /* Stat tile */
  .stat-tile {{
    background: var(--surface-card);
    border: 1px solid var(--border-hair);
    border-radius: 12px;
    padding: 20px 22px;
    height: 100%;
  }}
  .stat-tile .label {{
    font-size: 12px; font-weight: 600; letter-spacing: 0.06em;
    text-transform: uppercase; color: var(--ink-muted); margin: 0 0 4px 0;
  }}
  .stat-tile .delta {{
    float: right; font-size: 13px; font-weight: 600;
    display: inline-flex; align-items: center; gap: 4px;
    color: var(--ink-secondary);
  }}
  .stat-tile .value {{
    font-size: 40px; font-weight: 600; color: var(--ink-primary);
    line-height: 1.1; margin: 8px 0 6px 0; letter-spacing: -0.02em;
    clear: both;
  }}
  .stat-tile .caption {{ font-size: 12px; color: var(--ink-muted); margin-top: 10px; }}

  /* Notice cards */
  .notice {{ border-radius: 10px; padding: 14px 18px; font-size: 14px; }}
  .notice.error {{ background: var(--err-bg); border: 1px solid var(--err-border); color: var(--err-ink); }}
  .notice.warn  {{ background: var(--warn-bg); border: 1px solid var(--warn-border); color: var(--warn-ink); }}

  /* Stats table */
  table.stats {{
    width: 100%; border-collapse: collapse; font-size: 14px;
    font-variant-numeric: tabular-nums;
  }}
  table.stats thead th {{
    text-align: left; font-weight: 600; color: var(--ink-secondary);
    font-size: 12px; letter-spacing: 0.04em; text-transform: uppercase;
    padding: 10px 12px; border-bottom: 1px solid var(--border-hair);
  }}
  table.stats thead th.num {{ text-align: right; }}
  table.stats tbody td {{
    padding: 12px; border-bottom: 1px solid var(--border-hair);
    color: var(--ink-primary);
  }}
  table.stats tbody td.num {{ text-align: right; }}
  table.stats tbody tr:last-child td {{ border-bottom: none; }}

  /* Segmented control (frequência temporal) — white mode.
     Ataca o container, todos os labels (botões) e o botão checado. */
  [data-testid="stSegmentedControl"] div[role="radiogroup"] {{
    background: var(--surface-card) !important;
    border: 1px solid var(--border-hair) !important;
    border-radius: 8px !important;
    padding: 2px !important;
  }}
  [data-testid="stSegmentedControl"] label,
  [data-testid="stSegmentedControl"] label * {{
    background: var(--surface-card) !important;
    color: var(--ink-secondary) !important;
    border: none !important;
  }}
  [data-testid="stSegmentedControl"] label:has(input:checked),
  [data-testid="stSegmentedControl"] label:has(input:checked) *,
  [data-testid="stSegmentedControl"] label[aria-checked="true"],
  [data-testid="stSegmentedControl"] label[aria-checked="true"] * {{
    background: {t['grid']} !important;
    color: var(--ink-primary) !important;
    font-weight: 600 !important;
  }}

  /* Expander "Ver dados brutos" — white mode */
  [data-testid="stExpander"] {{
    background: var(--surface-card) !important;
    border: 1px solid var(--border-hair) !important;
    border-radius: 10px !important;
  }}
  [data-testid="stExpander"] > details {{
    background: var(--surface-card) !important;
    border-radius: 10px !important;
  }}
  [data-testid="stExpander"] summary {{
    background: var(--surface-card) !important;
    color: var(--ink-primary) !important;
    border-radius: 10px !important;
    font-size: 14px;
  }}

  /* DataFrame (dados brutos) — white mode.
     O Streamlit usa a grid do Glide; atacamos o container e descendentes. */
  [data-testid="stDataFrame"],
  [data-testid="stDataFrame"] > div,
  [data-testid="stDataFrame"] [class*="glideDataEditor"],
  [data-testid="stDataFrame"] [class*="gdg"] {{
    background: var(--surface-card) !important;
    color: var(--ink-primary) !important;
  }}
  [data-testid="stDataFrame"] [class*="gdg-cell"] {{
    background: var(--surface-card) !important;
    color: var(--ink-primary) !important;
  }}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_header(df_long):
    """Cabeçalho com o título e o período coberto pelos dados."""
    period_min = df_long["data_dt"].min().strftime("%b/%Y").replace(".", "").capitalize()
    period_max = df_long["data_dt"].max().strftime("%b/%Y").replace(".", "").capitalize()
    st.markdown(
        f"""
        <div class="app-header">
          <h1>BCB Tracker</h1>
          <p class="subtitle">Cotação do Dólar Comercial e Selic Meta — série histórica do Banco Central.</p>
          <p class="period">Período coberto: {period_min} → {period_max}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stat_tile(label, valor, variacao_pct, data_str, is_pct=False):
    """Card de métrica (hero + delta ▲/▼/—)."""
    formatted = f"{valor:.2f}%" if is_pct else f"R$ {valor:,.2f}"
    st.markdown(
        f"""
        <div class="stat-tile">
          <p class="label">{label}<span class="delta">{_variation_label(variacao_pct)}</span></p>
          <p class="value">{formatted}</p>
          <p class="caption">Última leitura: {data_str}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_overview(pivot_df):
    """Seção 'Visão geral' com o último valor e variação de cada série."""
    last = pivot_df.iloc[-1]
    cols = st.columns(2, gap="medium")
    for col, label, is_pct in [
        (cols[0], "Dólar Comercial", False),
        (cols[1], "Selic Meta", True),
    ]:
        with col:
            valor_col = "dolar" if not is_pct else "selic_meta"
            var_col = f"{valor_col}_variacao"
            # A última linha da view pode ter `dolar` ou `selic_meta` nulos
            # (ex.: fim de semana só publica Selic Meta em datas de Copom),
            # então pegamos o último valor não-nulo de cada série.
            valor = _ultimo_nao_nulo(pivot_df[valor_col])
            idx = pivot_df[valor_col].dropna().index[-1]
            render_stat_tile(
                label=label,
                valor=valor,
                variacao_pct=pivot_df.loc[idx, var_col],
                data_str=last["data"].strftime("%d/%m/%Y"),
                is_pct=is_pct,
            )


def render_charts(pivot_df, granularity):
    """Seção 'Frequência temporal' com os gráficos Dólar e Selic."""
    df_plot = pivot_df.copy().sort_values("data").set_index("data")
    aggregated, label = _window_or_resample(df_plot, granularity)
    if aggregated.empty:
        return

    chart_config = {"displayModeBar": False, "responsive": True, "scrollZoom": False}
    st.plotly_chart(build_chart_dolar(aggregated, granularity),
                    use_container_width=True, config=chart_config)
    st.plotly_chart(build_chart_selic(aggregated, granularity),
                    use_container_width=True, config=chart_config)
    st.markdown(
        f'<p style="color: var(--ink-muted); font-size: 12px; margin-top: 4px;">{label}.</p>',
        unsafe_allow_html=True,
    )


def render_summary(df_long):
    """Seção 'Resumo estatístico' com média, quartis, etc. por série."""
    summary = (
        df_long
        .groupby("tipo", as_index=False)["valor"]
        .agg(**STATS_AGG)
        .sort_values("tipo")
    )
    summary["tipo"] = summary["tipo"].map(TIPO_LABELS)
    is_dolar = (summary["tipo"] == "Dólar").to_numpy()
    for col in STATS_DISPLAY:
        summary[col] = _format_value_series(summary[col], is_dolar)

    rows = "".join(
        f"<tr><td>{row['tipo']}</td>"
        f"<td class='num'>{int(row['registros']):,}</td>"
        f"<td class='num'>{row['media']}</td>"
        f"<td class='num'>{row['minimo']}</td>"
        f"<td class='num'>{row['Q1']}</td>"
        f"<td class='num'>{row['Mediana']}</td>"
        f"<td class='num'>{row['Q3']}</td>"
        f"<td class='num'>{row['maximo']}</td>"
        f"<td class='num'>{row['desvio_padrao']}</td></tr>"
        for _, row in summary.iterrows()
    )
    st.markdown(
        f"""
        <table class="stats">
          <thead>
            <tr>
              <th>Série</th>
              <th class="num">Registros</th>
              <th class="num">Média</th>
              <th class="num">Mínimo</th>
              <th class="num">Q1</th>
              <th class="num">Mediana</th>
              <th class="num">Q3</th>
              <th class="num">Máximo</th>
              <th class="num">Desvio</th>
            </tr>
          </thead>
          <tbody>{rows}</tbody>
        </table>
        """,
        unsafe_allow_html=True,
    )


def render_raw_data(df_long):
    """Expander 'Ver dados brutos' com a tabela completa Data/Tipo/Valor/Variação."""
    df = (
        df_long[["data_dt", "tipo", "valor", "variacao"]]
        .sort_values(["data_dt", "tipo"], ascending=[False, True])
        .reset_index(drop=True)
    )
    df["tipo"] = df["tipo"].map(TIPO_LABELS)
    is_dolar = (df["tipo"] == "Dólar").to_numpy()
    df["valor_formatado"] = _format_value_series(df["valor"], is_dolar)
    # A variação já vem da view; formatamos com o mesmo padrão ▲/▼/— dos tiles.
    df["variacao_formatada"] = _variation_labels(df["variacao"])

    st.dataframe(
        df[["data_dt", "tipo", "valor_formatado", "variacao_formatada"]],
        use_container_width=True,
        hide_index=True,
        column_config={
            "data_dt":            st.column_config.DatetimeColumn("Data", format="DD/MM/YYYY"),
            "tipo":               st.column_config.TextColumn("Tipo"),
            "valor_formatado":    st.column_config.TextColumn("Valor"),
            "variacao_formatada": st.column_config.TextColumn("Variação"),
        },
    )
