from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from google.oauth2.service_account import Credentials
from dash import dcc, html, Input, Output
import dash
import dash_table
import plotly.graph_objects as go
import pandas as pd
import os
import json

# 환경 변수에서 서비스 계정 JSON 키를 읽어옴
service_account_info = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')

# 문자열로 저장된 JSON 데이터를 다시 딕셔너리로 변환
if service_account_info:
    service_account_info = json.loads(service_account_info)
    credentials = Credentials.from_service_account_info(service_account_info)

    # BigQuery 클라이언트 생성
    client = bigquery.Client(credentials=credentials, project=credentials.project_id)
else:
    raise Exception("Google Cloud 자격 증명을 찾을 수 없습니다.")

# market cap 가져오기
sql1 = f"""
SELECT
    *
  FROM
    `newbuja.finance.market_cap`;
"""
# nasdaq 가져오기
sql2 = f"""
SELECT
    *
  FROM
    `newbuja.finance.nasdaq`;
"""
# stock 가져오기
sql3 = f"""
SELECT
    *
  FROM
    `newbuja.finance.stock`;
"""

# 데이터프레임 변환
market_cap_data = client.query(sql1).to_dataframe().sort_values(by='Cap Rank', ascending=True)
nasdaq_data = client.query(sql2).to_dataframe()
stock_data = client.query(sql3).to_dataframe()

# 날짜 형식 변환
nasdaq_data['Date'] = pd.to_datetime(nasdaq_data['Date'])
stock_data['Date'] = pd.to_datetime(stock_data['Date'])

# 날짜순 정렬
nasdaq_data = nasdaq_data.sort_values(by='Date', ascending=True)
stock_data = stock_data.sort_values(by='Date', ascending=True)

# Ticker 리스트를 Cap Rank 기준으로 정렬
sorted_tickers = market_cap_data.sort_values(by='Cap Rank')['Ticker'].unique()

# Dash 애플리케이션 생성
app = dash.Dash(__name__)
server = app.server

# 레이아웃 구성
app.layout = html.Div([

    # 상단 구역
    html.Div([
        html.H1("American Dream !"),
        html.H2("시가총액 상위 10위 Daily Status"),
        dash_table.DataTable(
            id='market-cap-table',
            columns=[{'name': col, 'id': col} for col in market_cap_data.columns[0:]],
            data=market_cap_data.iloc[:, :].head(10).to_dict('records'),
            style_table={'overflowX': 'auto'},
            style_cell={'textAlign': 'center'},
            fixed_columns={'headers': True, 'data': 1},  # 첫 열을 고정
            page_size=10  # 최대 10개 행 표시
        )
    ], style={'border': '3px solid #ddd', 'padding': '10px'}),  # 상단 구획 나눔

    # 중단 구역
    html.Div([
        html.Div([
            html.H2("Top10 Chart", style={'margin-left': '10px'}),
            dcc.Dropdown(
                id='ticker-dropdown',
                options=[{'label': ticker, 'value': ticker} for ticker in sorted_tickers],
                value=sorted_tickers[0],  # 기본값으로 Cap Rank가 가장 높은 티커 선택
                clearable=False,
                style={'width': '95%', 'margin': 'auto'}
            ),
            dcc.Graph(
                id='candle-chart', 
                style={
                    'height': '400px',
                    'width': '100%',
                    'padding': '0',
                    'margin': '0'
                },
                figure={
                    'layout': {
                        'plot_bgcolor': 'white',  # 그래프 영역 배경을 흰색으로 설정
                        'paper_bgcolor': 'white'  # 전체 그래프 배경을 흰색으로 설정
                    }
                }
            )
        ], style={'width': '100%', 'display': 'inline-block', 'verticalAlign': 'top'}),
    ], style={'border': '3px solid #ddd', 'padding': '0px'}),  # 중단 구획 나눔
    
    # 하단 구역
    html.Div([
        html.Div([
            html.H2("NASDAQ", style={'text-align': 'center'}),
            dash_table.DataTable(
                id='nasdaq-recent-table',
                columns=[
                    {'name': 'Date', 'id': 'Date'},
                    {'name': 'Change(%)', 'id': 'Change(%)'},
                    {'name': '전고점비율', 'id': 'High_Current_ratio'}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'center'},
                fixed_columns={'headers': True, 'data': 1},  # 첫 열을 고정
                page_size=30  # 최대 30개 행 표시
            )
        ], style={'width': '48%', 'display': 'inline-block', 'verticalAlign': 'top', 'margin-right': '2%'}),
        html.Div([
            html.H2("Top10 Status", style={'text-align': 'center'}),
            dash_table.DataTable(
                id='stock-recent-table',
                columns=[
                    {'name': 'Close', 'id': 'Close'},
                    {'name': 'Change(%)', 'id': 'Change(%)'},
                    {'name': '전고점비율', 'id': 'High_Current_ratio'}
                ],
                style_table={'overflowX': 'auto'},
                style_cell={'textAlign': 'center'},
                page_size=30  # 최대 30개 행 표시
            )
        ], style={'width': '50%', 'display': 'inline-block', 'verticalAlign': 'top'}),

    ], style={'border': '3px solid #ddd', 'padding': '10px'}),  # 하단 구획 나눔
    dcc.Interval(
        id='interval-component',
        interval=3600*1000,  # 1시간 마다 호출 (필요에 따라 조정 가능)
        n_intervals=0  # 페이지 로드 시 한 번 실행
    )
])
##################################################################################################
# 콜백 설정: 나스닥 테이블 업데이트
@app.callback(
    Output('nasdaq-recent-table', 'data'),
    [Input('interval-component', 'n_intervals')]
)

def update_nasdaq_chart_and_table(n_intervals):
    df = nasdaq_data.copy()

    # 전날 대비 종가 변동률 계산
    df['Previous Close'] = df['Close'].shift(1)
    df['Change(%)'] = ((df['Close'] - df['Previous Close']) / df['Previous Close'] * 100).round(2)

    # NaN 값을 0으로 처리하여 초기 데이터 표시 문제 해결
    df.fillna(0, inplace=True)

    # 최근 30영업일 데이터 추출 및 최신 날짜가 위로 오도록 정렬
    recent_30_days = df.tail(30).sort_values(by='Date', ascending=False)
    recent_30_days['Date'] = recent_30_days['Date'].dt.strftime('%Y-%m-%d')  # 날짜 형식 변경

    # 사용하지 않는 컬럼 제거 및 소수점 2자리까지 반올림
    recent_30_days = recent_30_days[['Date', 'High', 'Low', 'Close', 'Change(%)','High_Current_ratio']]
    recent_30_days['High'] = recent_30_days['High'].round(2)
    recent_30_days['Low'] = recent_30_days['Low'].round(2)
    recent_30_days['Close'] = recent_30_days['Close'].round(2)

    return recent_30_days.to_dict('records')

#################################################################################################

# 콜백 설정: Top10 캔들차트와 테이블 업데이트
@app.callback(
    [Output('candle-chart', 'figure'),
     Output('stock-recent-table', 'data')],
    [Input('ticker-dropdown', 'value')]
)
def update_stock_chart_and_table(selected_ticker):
    df = stock_data[stock_data['Ticker'] == selected_ticker].copy()

    # 전날 대비 종가 변동률 계산
    df['Previous Close'] = df['Close'].shift(1)
    df['Change(%)'] = ((df['Close'] - df['Previous Close']) / df['Previous Close'] * 100).round(2)

    # NaN 값을 0으로 처리하여 초기 데이터 표시 문제 해결
    df.fillna(0, inplace=True)

    # 최근 30영업일 데이터 추출 및 최신 날짜가 위로 오도록 정렬
    recent_30_days = df.tail(30).sort_values(by='Date', ascending=False)
    recent_30_days['Date'] = recent_30_days['Date'].dt.strftime('%Y-%m-%d')  # 날짜 형식 변경

    # 사용하지 않는 컬럼 제거 및 소수점 2자리까지 반올림
    recent_30_days = recent_30_days[['Date', 'High', 'Low', 'Close', 'Change(%)','High_Current_ratio']]
    recent_30_days['High'] = recent_30_days['High'].round(2)
    recent_30_days['Low'] = recent_30_days['Low'].round(2)
    recent_30_days['Close'] = recent_30_days['Close'].round(2)

    # 상승일과 하락일 분리
    increasing_days = df[df['Close'] >= df['Previous Close']]
    decreasing_days = df[df['Close'] < df['Previous Close']]

    fig = go.Figure()

    # 상승일 캔들차트 추가 (빨간색)
    fig.add_trace(go.Candlestick(
        x=increasing_days['Date'],
        open=increasing_days['Open'],
        high=increasing_days['High'],
        low=increasing_days['Low'],
        close=increasing_days['Close'],
        increasing_line_color='red',
        increasing_fillcolor='red',
        hoverinfo='text',
        text=[f'Date: {d.strftime("%Y/%m/%d")}<br>'
              f'Open: {o:.1f}<br>'
              f'High: {h:.1f}<br>'
              f'Low: {l:.1f}<br>'
              f'Close: {c:.1f} ({cc:+.2f}%)'
              for d, o, h, l, c, cc in zip(
                  increasing_days['Date'], increasing_days['Open'], increasing_days['High'],
                  increasing_days['Low'], increasing_days['Close'], increasing_days['Change(%)']
              )]
    ))

    # 하락일 캔들차트 추가 (밝은 파란색)
    fig.add_trace(go.Candlestick(
        x=decreasing_days['Date'],
        open=decreasing_days['Open'],
        high=decreasing_days['High'],
        low=decreasing_days['Low'],
        close=decreasing_days['Close'],
        decreasing_line_color='#1E90FF',
        decreasing_fillcolor='#1E90FF',
        hoverinfo='text',
        text=[f'Date: {d.strftime("%Y/%m/%d")}<br>'
              f'Open: {o:.1f}<br>'
              f'High: {h:.1f}<br>'
              f'Low: {l:.1f}<br>'
              f'Close: {c:.1f} ({cc:+.2f}%)'
              for d, o, h, l, c, cc in zip(
                  decreasing_days['Date'], decreasing_days['Open'], decreasing_days['High'],
                  decreasing_days['Low'], decreasing_days['Close'], decreasing_days['Change(%)']
              )]
    ))

    # 차트 레이아웃 설정 및 rangeslider 및 날짜 형식 추가
    fig.update_layout(
        xaxis=dict(
            title='Date',
            tickformat='%Y/%m/%d',  # 날짜 형식을 YYYY/MM/DD로 설정
            rangeslider=dict(visible=True, thickness=0.1)  # rangeslider 활성화 및 두께 설정
        ),
        yaxis=dict(
            title='Stock Price',
            autorange=True  # y축 범위를 자동으로 조정
        ),
        showlegend=False  # 범례 숨김
    )

    return fig, recent_30_days.to_dict('records')

# 앱 실행
if __name__ == '__main__':
    app.run_server(debug=True)
