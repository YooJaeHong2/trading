"""
American Dream - 미국 시가총액 TOP 100 대시보드

페이지
  /         : 시가총액 상위 100개 종목 2년 일봉 차트
  /top10    : 상위 10개 종목 기간별 가격 변동률
  /leader   : 시가총액 1위 기업 최고점 대비 낙폭 모니터링

실행
  pip install -r requirements.txt
  python app.py                 # http://127.0.0.1:8050
  DEMO_DATA=1 python app.py     # 네트워크 없이 합성 데이터로 UI 확인
  gunicorn app:server           # 배포
"""
import dash
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, dash_table, dcc, html
from plotly.subplots import make_subplots

from data import PERIODS, fmt_cap, get_data, period_return

UP, DOWN = "#e5383b", "#1e88e5"          # 기존 대시보드와 동일: 상승 빨강 / 하락 파랑
INK, MUTED, GRID, CARD, BG = "#1f2328", "#6b7280", "#e5e7eb", "#ffffff", "#f5f6f8"
FONT = '-apple-system,BlinkMacSystemFont,"Segoe UI","Apple SD Gothic Neo","Malgun Gothic",sans-serif'
LINE_COLORS = ["#2563eb", "#e5383b", "#16a34a", "#f59e0b", "#7c3aed",
               "#0891b2", "#db2777", "#65a30d", "#ea580c", "#475569"]

app = dash.Dash(__name__, title="US Top 100 Dashboard", suppress_callback_exceptions=True)
server = app.server

app.index_string = """<!DOCTYPE html>
<html><head>{%metas%}<title>{%title%}</title>{%favicon%}{%css%}
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body{margin:0;background:""" + BG + """;color:""" + INK + """;
       font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Apple SD Gothic Neo","Malgun Gothic",sans-serif}
  .wrap{max-width:1280px;margin:0 auto;padding:16px}
  .nav{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-bottom:16px}
  .nav h1{font-size:20px;margin:0 16px 0 0}
  .nav a{padding:8px 14px;border-radius:8px;text-decoration:none;color:""" + INK + """;font-weight:600;font-size:14px}
  .nav a:hover{background:#e9ecf1}
  .nav a.active{background:""" + INK + """;color:#fff}
  .card{background:""" + CARD + """;border:1px solid """ + GRID + """;border-radius:12px;padding:16px;margin-bottom:16px}
  .card h2{font-size:16px;margin:0 0 12px}
  .muted{color:""" + MUTED + """;font-size:13px}
  .grid2{display:grid;grid-template-columns:340px 1fr;gap:16px}
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:16px}
  .kpi{background:""" + CARD + """;border:1px solid """ + GRID + """;border-radius:12px;padding:14px}
  .kpi .l{font-size:12px;color:""" + MUTED + """}
  .kpi .v{font-size:24px;font-weight:700;margin-top:4px;font-variant-numeric:tabular-nums}
  .kpi .s{font-size:12px;color:""" + MUTED + """;margin-top:2px}
  .badge{display:inline-block;padding:4px 10px;border-radius:999px;font-weight:700;font-size:13px}
  .row{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:8px}
  @media (max-width:900px){.grid2{grid-template-columns:1fr}}
</style></head>
<body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body></html>"""

NAV = [("/", "TOP 100 차트"), ("/top10", "TOP 10 변동률"), ("/leader", "1위 기업 고점 모니터")]


def base_layout(fig, height):
    fig.update_layout(
        height=height, margin=dict(l=50, r=20, t=70, b=30),
        plot_bgcolor="white", paper_bgcolor="white", font=dict(color=INK, size=12),
        hovermode="x unified", legend=dict(orientation="h", y=1.02, yanchor="bottom", x=1, xanchor="right"),
    )
    fig.update_xaxes(gridcolor=GRID, showspikes=True, spikemode="across", spikethickness=1)
    fig.update_yaxes(gridcolor=GRID)
    return fig


def pct_color(v):
    return UP if v > 0 else DOWN if v < 0 else INK


app.layout = html.Div(className="wrap", children=[
    dcc.Location(id="url"),
    html.Div(id="nav", className="nav"),
    html.Div(id="page"),
    html.Div(id="updated", className="muted"),
    dcc.Interval(id="tick", interval=3600 * 1000, n_intervals=0),  # 1시간마다 데이터 신선도 확인
])


@app.callback(Output("nav", "children"), Output("page", "children"), Output("updated", "children"),
              Input("url", "pathname"), Input("tick", "n_intervals"))
def route(path, _):
    d = get_data()
    nav = [html.H1("🇺🇸 American Dream")] + [
        dcc.Link(label, href=href, className="active" if path == href else "") for href, label in NAV]
    page = {"/top10": page_top10, "/leader": page_leader}.get(path, page_top100)(d)
    note = f"데이터 기준: {d.updated_at:%Y-%m-%d %H:%M} · 출처 Yahoo Finance (수정주가)"
    if d.demo:
        note += " · ⚠ DEMO_DATA=1 합성 데이터"
    return nav, page, note


# =========================================================================== #
# 1. TOP 100 차트
# =========================================================================== #
def page_top100(d):
    r = d.ranking.copy()
    r["시가총액"] = r["MarketCap"].map(fmt_cap)
    r["1일(%)"] = [round(period_return(d.prices[t]["Close"], 1), 2) for t in r["Ticker"]]
    r["2년(%)"] = [round(period_return(d.prices[t]["Close"], None), 1) for t in r["Ticker"]]
    r["종가"] = r["Close"].round(2)
    cols = ["Rank", "Ticker", "시가총액", "종가", "1일(%)", "2년(%)"]
    pct_styles = []
    for c in ["1일(%)", "2년(%)"]:
        pct_styles += [
            {"if": {"filter_query": f"{{{c}}} > 0", "column_id": c}, "color": UP},
            {"if": {"filter_query": f"{{{c}}} < 0", "column_id": c}, "color": DOWN},
        ]
    options = [{"label": f"{row.Rank}. {row.Ticker} · {row.Name}", "value": row.Ticker}
               for row in r.itertuples()]
    return html.Div(className="grid2", children=[
        html.Div(className="card", children=[
            html.H2("시가총액 순위 TOP 100"),
            html.Div("행을 클릭하면 차트가 바뀝니다", className="muted", style={"marginBottom": "8px"}),
            dash_table.DataTable(
                id="rank-table", data=r[cols].to_dict("records"),
                columns=[{"name": c, "id": c} for c in cols],
                sort_action="native", filter_action="native", page_size=20,
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "center", "fontSize": 13, "padding": "4px",
                            "fontFamily": FONT, "border": f"1px solid {GRID}"},
                style_header={"fontWeight": 700, "backgroundColor": BG},
                style_data_conditional=pct_styles,
            ),
        ]),
        html.Div(className="card", children=[
            html.Div(className="row", children=[
                dcc.Dropdown(id="ticker", options=options, value=r["Ticker"].iloc[0],
                             clearable=False, style={"flex": "1", "minWidth": "260px"}),
                dcc.RadioItems(id="ctype", value="candle", inline=True,
                               options=[{"label": " 캔들 ", "value": "candle"},
                                        {"label": " 라인 ", "value": "line"}]),
            ]),
            html.Div(id="ticker-summary", className="row"),
            dcc.Graph(id="price-chart", config={"displaylogo": False}),
        ]),
    ])


@app.callback(Output("ticker", "value"),
              Input("rank-table", "active_cell"),
              State("rank-table", "derived_viewport_data"), prevent_initial_call=True)
def pick_from_table(cell, rows):
    if not cell or not rows:
        raise dash.exceptions.PreventUpdate
    return rows[cell["row"]]["Ticker"]


@app.callback(Output("price-chart", "figure"), Output("ticker-summary", "children"),
              Input("ticker", "value"), Input("ctype", "value"))
def draw_price(tk, ctype):
    d = get_data()
    df = d.prices[tk].copy()
    df["Chg"] = df["Close"].pct_change() * 100
    info = d.ranking.set_index("Ticker").loc[tk]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22], vertical_spacing=0.03)
    hover = [f"O {o:,.2f}  H {h:,.2f}  L {l:,.2f}  C {c:,.2f} ({g:+.2f}%)"
             for o, h, l, c, g in zip(df.Open, df.High, df.Low, df.Close, df.Chg.fillna(0))]
    if ctype == "candle":
        fig.add_trace(go.Candlestick(
            x=df.index, open=df.Open, high=df.High, low=df.Low, close=df.Close, name=tk,
            increasing=dict(line_color=UP, fillcolor=UP), decreasing=dict(line_color=DOWN, fillcolor=DOWN),
            text=hover, hoverinfo="x+text"), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=df.index, y=df.Close, name=tk, line=dict(color=LINE_COLORS[0], width=2),
                                 text=hover, hoverinfo="x+text"), row=1, col=1)
    for w, col in [(20, "#f59e0b"), (60, "#16a34a"), (120, "#7c3aed")]:
        fig.add_trace(go.Scatter(x=df.index, y=df.Close.rolling(w).mean(), name=f"MA{w}",
                                 line=dict(color=col, width=1.2), hoverinfo="skip"), row=1, col=1)
    vol_colors = [UP if c >= o else DOWN for o, c in zip(df.Open, df.Close)]
    fig.add_trace(go.Bar(x=df.index, y=df.Volume, marker_color=vol_colors, name="거래량",
                         opacity=0.6, hovertemplate="%{y:,.0f}"), row=2, col=1)
    base_layout(fig, 560)
    fig.update_layout(xaxis_rangeslider_visible=False, showlegend=True)
    fig.update_xaxes(tickformat="%Y/%m", rangebreaks=[dict(bounds=["sat", "mon"])])
    fig.update_xaxes(row=1, col=1, rangeselector=dict(x=0, y=1.02, yanchor="bottom", buttons=[
        dict(count=1, label="1M", step="month", stepmode="backward"),
        dict(count=3, label="3M", step="month", stepmode="backward"),
        dict(count=6, label="6M", step="month", stepmode="backward"),
        dict(count=1, label="YTD", step="year", stepmode="todate"),
        dict(count=1, label="1Y", step="year", stepmode="backward"),
        dict(step="all", label="2Y")]))
    fig.update_yaxes(title_text="가격($)", row=1, col=1)
    fig.update_yaxes(title_text="거래량", row=2, col=1)

    last, chg = df.Close.iloc[-1], df.Chg.iloc[-1]
    hi = df.Close.max()
    summary = [
        html.Span(f"#{int(info.Rank)} {tk}", style={"fontWeight": 700, "fontSize": "18px"}),
        html.Span(info.Name, className="muted"),
        html.Span(f"${last:,.2f}", style={"fontWeight": 700}),
        html.Span(f"{chg:+.2f}%", style={"color": pct_color(chg), "fontWeight": 700}),
        html.Span(f"시총 {fmt_cap(info.MarketCap)}", className="muted"),
        html.Span(f"2년 고점 대비 {(last / hi - 1) * 100:+.1f}%", className="muted"),
    ]
    return fig, summary


# =========================================================================== #
# 2. TOP 10 변동률
# =========================================================================== #
def page_top10(d):
    top = d.ranking.head(10)
    rows = []
    for row in top.itertuples():
        c = d.prices[row.Ticker]["Close"]
        rec = {"Rank": row.Rank, "Ticker": row.Ticker, "종목명": row.Name,
               "시가총액": fmt_cap(row.MarketCap), "종가": round(c.iloc[-1], 2)}
        for label, p in PERIODS:
            rec[label] = round(period_return(c, p), 2)
        rows.append(rec)
    labels = [l for l, _ in PERIODS]
    styles = []
    for l in labels:  # 변동 폭에 따라 셀 배경 농도 조절
        for lo, hi, a in [(0, 5, .10), (5, 20, .22), (20, 1e9, .38)]:
            styles.append({"if": {"filter_query": f"{{{l}}} > {lo} && {{{l}}} <= {hi}", "column_id": l},
                           "backgroundColor": f"rgba(229,56,59,{a})", "color": UP})
            styles.append({"if": {"filter_query": f"{{{l}}} < -{lo} && {{{l}}} >= -{hi}", "column_id": l},
                           "backgroundColor": f"rgba(30,136,229,{a})", "color": DOWN})
    return html.Div([
        html.Div(className="card", children=[
            html.H2("시가총액 TOP 10 · 기간별 가격 변동률 (%)"),
            dash_table.DataTable(
                data=rows, sort_action="native",
                columns=[{"name": c, "id": c} for c in ["Rank", "Ticker", "종목명", "시가총액", "종가"] + labels],
                style_table={"overflowX": "auto"},
                style_cell={"textAlign": "center", "fontSize": 13, "padding": "6px",
                            "fontFamily": FONT, "border": f"1px solid {GRID}"},
                style_cell_conditional=[{"if": {"column_id": "종목명"}, "textAlign": "left"}],
                style_header={"fontWeight": 700, "backgroundColor": BG},
                style_data_conditional=styles),
        ]),
        html.Div(className="card", children=[
            html.Div(className="row", children=[
                html.H2("기간 선택", style={"margin": 0}),
                dcc.RadioItems(id="t10-period", value="3개월", inline=True,
                               options=[{"label": f" {l} ", "value": l} for l in labels]),
            ]),
            dcc.Graph(id="t10-bar", config={"displaylogo": False}),
            dcc.Graph(id="t10-line", config={"displaylogo": False}),
        ]),
    ])


@app.callback(Output("t10-bar", "figure"), Output("t10-line", "figure"), Input("t10-period", "value"))
def draw_top10(label):
    d = get_data()
    top = d.ranking.head(10)["Ticker"].tolist()
    period = dict(PERIODS)[label]

    rets = [(t, period_return(d.prices[t]["Close"], period)) for t in top]
    rets.sort(key=lambda x: x[1], reverse=True)
    bar = go.Figure(go.Bar(
        x=[t for t, _ in rets], y=[v for _, v in rets], marker_color=[pct_color(v) for _, v in rets],
        text=[f"{v:+.1f}%" for _, v in rets], textposition="outside", cliponaxis=False,
        hovertemplate="%{x}: %{y:+.2f}%<extra></extra>"))
    base_layout(bar, 320)
    bar.update_layout(title=dict(text=f"{label} 수익률 순위", font_size=14), hovermode="closest")
    bar.update_yaxes(ticksuffix="%", zeroline=True, zerolinecolor=MUTED)

    line = go.Figure()
    for i, t in enumerate(top):
        c = d.prices[t]["Close"]
        if period == "YTD":
            prev = c[c.index < pd.Timestamp(c.index[-1].year, 1, 1)]
            c = c.loc[prev.index[-1]:] if len(prev) else c
        elif period is not None:
            c = c.iloc[-1 - period:]
        rel = (c / c.iloc[0] - 1) * 100
        line.add_trace(go.Scatter(x=rel.index, y=rel, name=t, line=dict(color=LINE_COLORS[i], width=1.8),
                                  hovertemplate=f"{t} %{{y:+.2f}}%<extra></extra>"))
    base_layout(line, 440)
    line.update_layout(title=dict(text=f"{label} 누적 변동률 비교 (시작일 = 0%)", font_size=14))
    line.update_xaxes(tickformat="%Y/%m/%d")
    line.update_yaxes(ticksuffix="%", zeroline=True, zerolinecolor=MUTED)
    return bar, line


# =========================================================================== #
# 3. 1위 기업 최고점 대비 모니터
# =========================================================================== #
LEVELS = [(-5, "정상", "#16a34a"), (-10, "주의", "#f59e0b"), (-20, "조정", "#ea580c"), (-1e9, "하락장", "#dc2626")]


def status_of(dd):
    for th, name, col in LEVELS:
        if dd > th:
            return name, col
    return LEVELS[-1][1], LEVELS[-1][2]


def page_leader(d):
    top = d.ranking.iloc[0]
    h = d.leader_history
    last = h.iloc[-1]
    ath, ath_date = h.max(), h.idxmax()
    dd = (last / ath - 1) * 100
    since = (h.index[-1] - ath_date).days
    two = d.prices[top.Ticker]["Close"]
    dd2y_max = ((two / two.cummax() - 1) * 100).min()
    chg1 = period_return(two, 1)
    st, col = status_of(dd)
    to_ath = (ath / last - 1) * 100

    def kpi(label, value, sub="", color=INK):
        return html.Div(className="kpi", children=[
            html.Div(label, className="l"), html.Div(value, className="v", style={"color": color}),
            html.Div(sub, className="s")])

    return html.Div([
        html.Div(className="card", children=[
            html.Div(className="row", children=[
                html.H2(f"시가총액 1위 · {top.Ticker} ({top.Name})", style={"margin": 0}),
                html.Span(f"상태: {st}", className="badge", style={"background": col, "color": "white"}),
            ]),
            html.Div("상태 기준 (역대 최고 종가 대비): 정상 > -5% · 주의 -5~-10% · 조정 -10~-20% · 하락장 < -20%",
                     className="muted"),
        ]),
        html.Div(className="kpis", children=[
            kpi("현재가", f"${last:,.2f}", f"전일 대비 {chg1:+.2f}%", pct_color(chg1)),
            kpi("역대 최고 종가", f"${ath:,.2f}", f"{ath_date:%Y-%m-%d}"),
            kpi("최고점 대비", f"{dd:+.2f}%", "현재 낙폭", pct_color(dd) if dd < 0 else UP),
            kpi("고점 회복까지", f"{to_ath:+.2f}%", "필요 상승률"),
            kpi("고점 이후 경과", f"{since}일", "달력 기준"),
            kpi("최근 2년 최대 낙폭", f"{dd2y_max:.1f}%", "MDD", DOWN),
            kpi("시가총액", fmt_cap(top.MarketCap), "현재"),
        ]),
        html.Div(className="card", children=[
            html.Div(className="row", children=[
                html.H2("가격 · 최고점 · 낙폭", style={"margin": 0}),
                dcc.RadioItems(id="ld-range", value="2Y", inline=True,
                               options=[{"label": f" {x} ", "value": x} for x in ["6M", "1Y", "2Y", "5Y", "전체"]]),
            ]),
            dcc.Graph(id="ld-chart", config={"displaylogo": False}),
        ]),
        html.Div(className="card", children=[
            html.H2("최근 30영업일"),
            dash_table.DataTable(id="ld-table", page_size=30,
                                 style_table={"overflowX": "auto"},
                                 style_cell={"textAlign": "center", "fontSize": 13, "padding": "4px",
                                             "fontFamily": FONT, "border": f"1px solid {GRID}"},
                                 style_header={"fontWeight": 700, "backgroundColor": BG}),
        ]),
    ])


@app.callback(Output("ld-chart", "figure"), Output("ld-table", "data"), Output("ld-table", "columns"),
              Output("ld-table", "style_data_conditional"), Input("ld-range", "value"))
def draw_leader(rng):
    d = get_data()
    h = d.leader_history
    peak = h.cummax()                      # 전 기간 기준 누적 최고점
    dd = (h / peak - 1) * 100
    days = {"6M": 182, "1Y": 365, "2Y": 730, "5Y": 1826}.get(rng)
    start = h.index[-1] - pd.Timedelta(days=days) if days else h.index[0]
    hs, ps, ds = h[start:], peak[start:], dd[start:]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.62, 0.38], vertical_spacing=0.05)
    fig.add_trace(go.Scatter(x=hs.index, y=hs, name="종가", line=dict(color=LINE_COLORS[0], width=2),
                             hovertemplate="$%{y:,.2f}"), row=1, col=1)
    fig.add_trace(go.Scatter(x=ps.index, y=ps, name="누적 최고점", line=dict(color=UP, width=1.4, dash="dot"),
                             hovertemplate="$%{y:,.2f}"), row=1, col=1)
    fig.add_trace(go.Scatter(x=ds.index, y=ds, name="최고점 대비(%)", fill="tozeroy",
                             line=dict(color=DOWN, width=1.2), fillcolor="rgba(30,136,229,0.18)",
                             hovertemplate="%{y:.2f}%"), row=2, col=1)
    for th, name, col in LEVELS[:-1]:
        fig.add_hline(y=th, line=dict(color=col, width=1, dash="dash"), row=2, col=1,
                      annotation_text=f"{th}%", annotation_position="right",
                      annotation_font=dict(color=col, size=11))
    base_layout(fig, 600)
    fig.update_xaxes(tickformat="%Y/%m")
    fig.update_yaxes(title_text="가격($)", row=1, col=1)
    fig.update_yaxes(title_text="낙폭", ticksuffix="%", row=2, col=1, range=[min(ds.min() * 1.1, -25), 2])

    t = pd.DataFrame({"Close": h, "Chg": h.pct_change() * 100, "DD": dd}).tail(30).iloc[::-1]
    data = [{"Date": f"{i:%Y/%m/%d}", "Close": round(r.Close, 2),
             "변동(%)": round(r.Chg, 2), "전고점(%)": round(r.DD, 2)} for i, r in t.iterrows()]
    cols = [{"name": c, "id": c} for c in ["Date", "Close", "변동(%)", "전고점(%)"]]
    styles = [
        {"if": {"filter_query": "{변동(%)} > 0", "column_id": "변동(%)"}, "color": UP},
        {"if": {"filter_query": "{변동(%)} < 0", "column_id": "변동(%)"}, "color": DOWN},
    ] + [{"if": {"filter_query": f"{{전고점(%)}} <= {th0} && {{전고점(%)}} > {th1}", "column_id": "전고점(%)"},
          "color": col, "fontWeight": 700}
         for (th0, _, _), (th1, _, col) in zip([(0, 0, 0)] + LEVELS[:-1], LEVELS)]
    return fig, data, cols, styles


if __name__ == "__main__":
    import os
    get_data()  # 첫 요청 전에 데이터 미리 로드
    app.run(debug=False, host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "8050")))
