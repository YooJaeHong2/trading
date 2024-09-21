import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output

# Dash 애플리케이션 초기화
app = dash.Dash(__name__)
server = app.server

# 애플리케이션 레이아웃 설정
app.layout = html.Div([
    dcc.Input(id='my-input', value='초기값', type='text'),
    html.Div(id='my-output') ])

# 콜백 정의
@app.callback(
    Output(component_id='my-output', component_property='children'),
    [Input(component_id='my-input', component_property='value')])
def update_output_div(input_value):
    return f'입력된 값: {input_value}'

if __name__ == '__main__':
    app.run_server(debug=True)  # 서버 실행
