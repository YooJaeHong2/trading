from google.cloud import bigquery
from google.cloud.exceptions import NotFound
from google.oauth2.service_account import Credentials
import dash
from dash import html
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

# data table 가져오기
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
