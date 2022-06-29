import dash.exceptions
import plotly.graph_objs
from dash import Dash, dcc, html, ctx
import dash_mantine_components as dmc
from dash.dependencies import Input, Output, State
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objs as go
import pandas as pd
from update_date import DataWorker
import logging
import base64
from auth import enable_dash_auth
from threading import Lock
from datetime import datetime


WRITE_LOG_TO_FILE = False
LOG_FORMAT = '%(name)s (%(levelname)s) %(asctime)s: %(message)s'
LOG_LEVEL = logging.INFO
logger = logging.getLogger('main')

if WRITE_LOG_TO_FILE:
    logging.basicConfig(filename='dash.txt', filemode='w', format=LOG_FORMAT, level=LOG_LEVEL,
                        datefmt='%d/%m/%y %H:%M:%S')
else:
    logging.basicConfig(format=LOG_FORMAT, level=LOG_LEVEL, datefmt='%d/%m/%y %H:%M:%S')


def b64_image(image_filename):
    with open(image_filename, 'rb') as f:
        image = f.read()
    return 'data:image/png;base64,' + base64.b64encode(image).decode('utf-8')


app = Dash(__name__, title='Склад ЛК', external_stylesheets=[dbc.themes.MINTY],
           meta_tags=[{"name": "viewport",
                       'content': 'width=device-width, initial-scale=1.0'}])
enable_dash_auth(app)
lock = Lock()
db = DataWorker(lock)


def dates_calc(start_date: str, end_date: str) -> tuple[datetime, datetime]:
    """
    :param start_date: string
    :param end_date: string
    :return: touple of datetimes
    """
    if start_date is not None:
        start_date = pd.to_datetime(start_date).replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        start_date = db.df['Дата'].max().replace(hour=0, minute=0, second=0, microsecond=0)
    if end_date is not None:
        end_date = pd.to_datetime(end_date).replace(hour=23, minute=59, second=59, microsecond=0)
    else:
        end_date = db.df['Дата'].max().replace(hour=23, minute=59, second=59, microsecond=0)
    return start_date, end_date


def draw_main_graph(start_date: str, end_date: str) -> plotly.graph_objs.Figure:
    """
    Создание фигуры основного графика с заданиями
    :param start_date: string
    :param end_date: string
    :return: plotly figure
    """
    if db.df.empty:
        return px.scatter()
    start_date, end_date = dates_calc(start_date, end_date)
    fig = px.scatter(db.df[(db.df['Дата'] >= start_date) & (db.df['Дата'] <= end_date)], x="Дата",
                     y="ВремяВыполнения_m",
                     color="Легенда", hover_name="Ссылка", opacity=0.7, symbol='Статус',
                     color_discrete_sequence=px.colors.qualitative.Plotly,
                     hover_data=['ВремяРеакции_мин', 'БригадаОтветственный', 'ИнформацияОПолучателе', 'СпособДоставки',
                                 'Объем', 'Строк'],
                     labels={
                         "ВремяВыполнения_m": "Время выполнения, мин.",
                         "ВремяРеакции_m": "Время реакции, уровень",
                         "ВремяРеакции_мин": "Время реакции, мин.",
                         "Ссылка": "Документ",
                         "СпособДоставки": 'Способ доставки',
                         "ИнформацияОПолучателе": 'Получатель'
                     },
                     category_orders={
                         'Легенда': ['Норма', 'Клиент ждет дольше 2х минут', 'Моментальное исполнение',
                                     'Выполнение дольше 2х часов',
                                     'Реакция дольше 2х минут'],
                         'Статус': ['Выполнено', 'В работе', 'Подготовлено', 'Выполнено с ошибками'],
                         'СпособДоставки': ['Самовывоз', 'До клиента']
                     }, title='Задания')
    fig.update_traces(marker={'size': 10,
                              'line': {'color': 'DarkSlateGrey', 'width': 1}
                              },
                      )
    fig.update_xaxes(
        tickformat="%H:%M\n%d.%m.%Y")
    return fig


def draw_load_graph(start_date: str, end_date: str) -> plotly.graph_objs.Figure:
    """
    Создание фигуры графика нагрузки на склад
    :param start_date: string
    :param end_date: string
    :return: plotly figure
    """
    if db.df.empty:
        return px.scatter()
    start_date, end_date = dates_calc(start_date, end_date)
    df_p = db.df[(db.df['Дата'] >= start_date) & (db.df['Дата'] <= end_date)]
    trace1 = go.Scatter(x=df_p['Дата'], y=df_p['Нагрузка'], mode='lines+markers', yaxis='y1',
                        name='Строк в работе')
    trace2 = go.Scatter(x=df_p['Дата'], y=df_p['Объем в работе'], mode='lines', yaxis='y2',
                        name='Объем, м<sup>3</sup> в работе')
    data = [trace1, trace2]

    layout = go.Layout(title='Нагрузка на склад',
                       xaxis=dict(tickformat="%H:%M\n%d.%m.%Y"),
                       yaxis=dict(title='Нагрузка (строк в работе)'),
                       yaxis2=dict(title='Объем, м<sup>3</sup>',
                                   overlaying='y',
                                   side='right'))
    fig = go.Figure(data=data, layout=layout)
    return fig


def draw_react_graph(start_date: str, end_date: str) -> plotly.graph_objs.Figure:
    """
    Создание фигуры графика среднеего времени реакции ответственных
    :param start_date: string
    :param end_date: string
    :return: plotly figure
    """
    if db.df.empty:
        return px.scatter()
    start_date, end_date = dates_calc(start_date, end_date)
    df_p = db.df[(db.df['Дата'] >= start_date) & (db.df['Дата'] <= end_date)].copy()
    df_p['Количество заданий'] = 1
    df_count = df_p[['БригадаОтветственный', 'Количество заданий']].groupby(by='БригадаОтветственный').sum()
    df_p = df_p[['БригадаОтветственный', 'ВремяРеакции']][df_p['БригадаОтветственный'] != '']\
        .groupby(by='БригадаОтветственный', as_index=False).mean()
    df_p['ВремяРеакции'] = (df_p['ВремяРеакции'] / 60).astype(int)
    df_p = pd.merge(df_p, df_count, how='left', on='БригадаОтветственный')

    fig = px.bar(df_p, x='ВремяРеакции', y='БригадаОтветственный', color='БригадаОтветственный',
                 title='Время реакции',
                 hover_data=['Количество заданий'],
                 labels={
                     "ВремяРеакции": "Среднее время реакции, мин.",
                     "БригадаОтветственный": ""
                 }, )
    fig.update_layout(showlegend=False)
    return fig


# ********************** the page **********************
app.layout = dbc.Container([
    # Header
    dbc.Row(
        dbc.Col(
            html.H3('Мониторинг склада',
                    className='text-center')
        )
    ),

    # data picker Row
    dbc.Row([
        dbc.Col([
            dmc.DateRangePicker(
                id="date-range-picker",
                label="Период",
                hideOutsideDates=True,
                style={"width": 330},
                locale="ru",
            )
        ], width={'size': 3, 'offset': 1}),
        dbc.Col(
            html.Button('Текущий день', id='btn_today', n_clicks=0, className='btn btn-outline-primary'),
            width={'size': 2, 'offset': 0}, align="end"
        )
    ], justify='start', className='g-0'),

    # Main graph Row
    dbc.Row(
        dbc.Col([
            dcc.Graph(id='main-graph'),
        ])
    ),

    # bottom graphs Row
    dbc.Row([

        dbc.Col(
            dcc.Graph(id='graph_load'), width={'size': 6}
        ),
        dbc.Col(
            dcc.Graph(id='graph_react_time'), width={'size': 6}
        )
    ]),
    dbc.Row(
        dbc.Col(
            dcc.Interval(
                id='interval-component',
                interval=30 * 1000,  # in milliseconds
                n_intervals=0
            )
        )
    )
], fluid=True)


@app.callback([Output('main-graph', 'figure'),
               Output('main-graph', 'animate'),
               Output('date-range-picker', 'minDate'),
               Output('date-range-picker', 'maxDate'),
               Output('date-range-picker', 'value'),
               Output('graph_load', 'figure'),
               Output('graph_load', 'animate'),
               Output('graph_react_time', 'figure'),
               ],
              [Input('interval-component', 'n_intervals'),
               Input('date-range-picker', 'value'),
               Input('btn_today', 'n_clicks')],
              prevent_initial_call=False)
def update_graph_live(n, value, n_clicks):
    if db.df.empty:
        return dash.no_update, dash.no_update, "", "", dash.no_update, dash.no_update, dash.no_update, dash.no_update
    else:
        if value is None:
            value = (None, None)
        animate = True
        if ctx.triggered_id in ['date-range-picker', 'btn_today']:
            animate = False
        with lock:
            if ctx.triggered_id == 'btn_today':
                return draw_main_graph(None, None), animate, "", "", (None, None), draw_load_graph(None, None), \
                       animate, draw_react_graph(None, None)
            return draw_main_graph(*value), animate, db.df['Дата'].min(), db.df['Дата'].max(), dash.no_update, \
                   draw_load_graph(*value), animate, draw_react_graph(*value)


if __name__ == '__main__':
    db.run()
    app.run_server(debug=False, host='0.0.0.0')
