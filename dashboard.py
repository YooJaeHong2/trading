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

# In place of something like this
@app.before_first_request
def create_tables():
    db.create_all()
    ...

# push context manually to app
with app.app_context():
    db.create_all()

# 레이아웃 생성
app.layout = html.Div([
    html.H4(children='US Agriculture Exports (2011)'),
    generate_table(df)
])

if __name__ == '__main__':
    # Dash 앱 실행
    app.run_server(debug=True)
