# import dash
# import dash_core_components as dcc
# import dash_html_components as html
# from dash.dependencies import Input, Output

# # Dash 애플리케이션 초기화
# app = dash.Dash(__name__)
# server = app.server

# # 애플리케이션 레이아웃 설정
# app.layout = html.Div([
#     dcc.Input(id='my-input', value='초기값', type='text'),
#     html.Div(id='my-output') ])

# # 콜백 정의
# @app.callback(
#     Output(component_id='my-output', component_property='children'),
#     [Input(component_id='my-input', component_property='value')])
# def update_output_div(input_value):
#     return f'입력된 값: {input_value}'

# if __name__ == '__main__':
#     app.run_server(debug=True)  # 서버 실행


import dash
from dash import html
import pandas as pd

# Pandas DataFrame 로드
df = pd.read_csv('https://gist.githubusercontent.com/chriddyp/c78bf172206ce24f77d6363a2d754b59/raw/c353e8ef842413cae56ae3920b8fd78468aa4cb2/usa-agricultural-exports-2011.csv')


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
    html.H4(children='US Agriculture Exports (2011)'),
    generate_table(df)
])

if __name__ == '__main__':
    # Dash 앱 실행
    app.run_server(debug=True)
