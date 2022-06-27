from datetime import datetime, timedelta
import threading
from env import SERVER, BASE, ROUTE, API_KEY, MAX_INTERVAL_DAYS, USER, PASSWORD
import requests
import json
from time import sleep
import logging
import pandas as pd
from threading import Lock


class DataWorker:
    logger = logging.getLogger('DataWorker')

    def __init__(self):
        self._df = pd.DataFrame()
        self.lock = Lock()
        self.update_data_thread = threading.Thread(target=self.threaded_func, args=())
        self.session = requests.Session()
        self.session.auth = (USER, PASSWORD)

    @property
    def df(self):
        with self.lock:
            return self._df

    @staticmethod
    def _date_to_str_1c(_date: datetime) -> str:
        return _date.strftime("%d.%m.%Y %H:%M:%S")

    def _get_data(self, _date: datetime) -> dict:
        try:
            text = self.session.get(f'''
                http://{SERVER}/{BASE}{ROUTE}?api_key={API_KEY}&date= {self._date_to_str_1c(_date)}
                ''').text
            # logger.info('get ok')
        except requests.exceptions.ConnectionError or requests.exceptions.ConnectTimeout as ex:
            self.logger.warning(ex)
            text = '{"data": []}'
        return json.loads(text)

    @staticmethod
    def _preprocessing_data(_df: pd.DataFrame) -> pd.DataFrame:
        if _df.empty:
            return _df

        def reaction_time_modify(x):
            _x = int(x / 60)
            if _x <= 2:
                return 1.
            elif 2 < _x <= 5:
                return 1.1
            elif _x > 5:
                return 1.2

        def work_time_modify(x):
            _x = round(x / 60)
            if _x > 180:
                return 180
            elif _x <= 0:
                return 1
            else:
                return _x

        def legend_func(react_time, work_time, status, ship_method):
            if status == 'Выполнено' or status == 'Выполнено с ошибками':
                if work_time < 30:
                    return 'Моментальное исполнение'
            if status == 'В работе' or status == 'Выполнено' or status == 'Выполнено с ошибками':
                if work_time > 7200:
                    return 'Выполнение дольше 2х часов'
                if react_time > 60:
                    return 'Реакция дольше 2х минут'
            if status == 'Подготовлено':
                if react_time > 60:
                    return 'Клиент ждет дольше 2х минут'
            return 'Норма'

        def react_time_reformat_func(_date, react_time, status):
            if status == 'Подготовлено':
                return (datetime.now() - _date).total_seconds()
            return react_time

        def work_time_reformat_func(start_work, work_time, status):
            if status == 'В работе':
                return (datetime.now() - start_work).total_seconds()
            return work_time

        _df['Статус'] = _df['Статус'].replace('Выполнено без ошибок', 'Выполнено')
        _df['ДатаОкончанияВыполнения'] = pd.to_datetime(_df['ДатаОкончанияВыполнения'], format='%d.%m.%Y %H:%M:%S',
                                                        errors='coerce')
        _df['ДатаНачалаВыполнения'] = pd.to_datetime(_df['ДатаНачалаВыполнения'], format='%d.%m.%Y %H:%M:%S',
                                                     errors='coerce')
        _df['Дата'] = pd.to_datetime(_df['Дата'], format='%d.%m.%Y %H:%M:%S', errors='coerce')
        _df['ИсполнитьК'] = pd.to_datetime(_df['ИсполнитьК'], format='%d.%m.%Y %H:%M:%S', errors='coerce')
        _df['ВремяРеакции'] = (_df['ДатаНачалаВыполнения'] - _df['Дата']).dt.total_seconds()
        _df['ВремяРеакции'] = _df['ВремяРеакции'].fillna(0)
        _df['ВремяРеакции'] = _df[['Дата', 'ВремяРеакции', 'Статус']].apply(lambda x: react_time_reformat_func(
            x['Дата'], x['ВремяРеакции'], x['Статус']), axis=1)
        _df['ВремяРеакции'] = _df['ВремяРеакции'].astype(int)
        _df['ВремяВыполнения'] = (_df['ДатаОкончанияВыполнения'] - _df['ДатаНачалаВыполнения']).dt.total_seconds()
        _df['ВремяВыполнения'] = _df['ВремяВыполнения'].fillna(0)
        _df['ВремяВыполнения'] = _df[['ДатаНачалаВыполнения', 'ВремяВыполнения', 'Статус']].apply(
            lambda x: work_time_reformat_func(x['ДатаНачалаВыполнения'], x['ВремяВыполнения'], x['Статус']), axis=1)
        _df['ВремяВыполнения'] = _df['ВремяВыполнения'].astype(int)
        _df['Легенда'] = _df[['ВремяРеакции', 'ВремяВыполнения', 'Статус', 'СпособДоставки']].apply(
            lambda x: legend_func(x['ВремяРеакции'], x['ВремяВыполнения'], x['Статус'], x['СпособДоставки']),
            axis=1)
        _df['ВремяРеакции_m'] = _df['ВремяРеакции'].apply(lambda x: reaction_time_modify(x))
        _df['ВремяВыполнения_m'] = _df['ВремяВыполнения'].apply(lambda x: work_time_modify(x))
        _df['month'] = _df['Дата'].dt.month
        return _df

    def _load_data(self, _df: pd.DataFrame) -> pd.DataFrame:
        if _df.empty:
            start_date = (datetime.now() - timedelta(days=MAX_INTERVAL_DAYS)).replace(hour=0, minute=0, second=0)
            _df = pd.json_normalize(self._get_data(start_date)['data'])
            _df = self._preprocessing_data(_df)
        else:
            last_date = _df['Дата'].max().replace(hour=0, minute=0, second=0)
            loaded_df = self._preprocessing_data(
                pd.json_normalize(self._get_data(last_date)['data'])
            )
            if not loaded_df.empty:
                _df = pd.concat([_df[_df['Дата'] < last_date], loaded_df], axis=0, ignore_index=True)
        return _df

    def threaded_func(self):
        while True:
            with self.lock:
                try:
                    self._df = self._load_data(self._df)
                except Exception as ex:
                    self.logger.error(ex)
            sleep(5)

    def run(self):
        self.update_data_thread.start()
