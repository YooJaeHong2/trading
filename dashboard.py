import dash
from dash import html
import pandas as pd
import os

# Pandas DataFrame 로드
# df = pd.read_csv('https://gist.githubusercontent.com/chriddyp/c78bf172206ce24f77d6363a2d754b59/raw/c353e8ef842413cae56ae3920b8fd78468aa4cb2/usa-agricultural-exports-2011.csv')

from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from google.oauth2.service_account import Credentials

# 서비스 계정 인증, BigQuery 클라이언트 객체 생성
JSON_PATH = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
credentials = Credentials.from_service_account_file(JSON_PATH)
client = bigquery.Client(credentials = credentials,
                         project = credentials.project_id)

sql = f"""
SELECT
    *
  FROM
    `newbuja.finance.market_cap`;
"""

# 데이터 조회 쿼리 실행 결과
query_job = client.query(sql)

# 데이터프레임 변환
df = query_job.to_dataframe()

# HTML 테이블 요소 파싱
def generate_table(dataframe, max_rows=10):
    return html.Table([
        html.Thead(
            html.Tr([html.Th(col) for col in dataframe.columns])
        ),
        html.Tbody([
            html.Tr([
                html.Td(dataframe.iloc[i][col]) for col in dataframe.columns
            ]) for i in range(min(len(dataframe), max_rows))
        ])
    ])


# Dash 앱 인스턴스 생성
app = dash.Dash(__name__)
server = app.server

# 레이아웃 생성
app.layout = html.Div([
    html.H4(children='World Market Cap Top10 List'),
    generate_table(df)
])

if __name__ == '__main__':
    # Dash 앱 실행
    app.run_server(debug=True)
