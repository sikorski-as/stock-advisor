import datetime
import itertools
import config
import requests
import json
import database.builder as builder
from database.models import Record, Model

"Epoch time dla lat 2014-2019, gdzie pierwszy element to 31.12.2014"
YEARS = [1419984000, 1451520000, 1483142400, 1514678400, 1546214400, 1577750400]

session = builder.Session()


def _retrieve_information(data: dict):
    general_info = data['Data']
    list_of_records = general_info['Data']
    attrs = ["time", "high", "low", "open", "close"]
    return [[record_info[attr] for attr in attrs] for record_info in list_of_records]


def _convert_time(info: iter):
    "Fajne do debugu czasu, lepiej sie czyta niz epoch"
    for value in info:
        value[0] = datetime.datetime.fromtimestamp(value[0])


def _create_records(currency: str, info: iter):
    return [Record(currency=currency, time=time, high=high, low=low, open=open, close=close)
            for time, high, low, open, close in info]


def _get_historical_data(fcurr: str, tcurr: str, limit: int, timestamp: int = None):
    """
    :param fcurr: Poszukiwana waluta
    :param tcurr: Waluta na ktora jest przeliczana
    :param limit: ilosc dni
    :param timestamp: ostatni dzien, epoch time

    Jesli chcemy dostac wszystkie wyniki z marca to podajemy ostatni dzien marca i limit na 30
    """
    if timestamp:
        url = f"https://min-api.cryptocompare.com/data/v2/histoday?fsym={fcurr}&tsym={tcurr}&toTs={timestamp}&limit={limit}&api_key={config.API_KEY}"
    else:
        url = f"https://min-api.cryptocompare.com/data/v2/histoday?fsym={fcurr}&tsym={tcurr}&limit={limit}&api_key={config.API_KEY}"
    print(url)
    with requests.Session() as session:
        response = session.get(url)
        data = json.loads(response.text)
        info = _retrieve_information(data)
        return _create_records(fcurr, info)


def get_current_data(fcurr: str, tcurr: str) -> float:
    "Pobiera aktualny kurs waluty"
    url = f"https://min-api.cryptocompare.com/data/price?fsym={fcurr}&tsyms={tcurr}"
    with requests.Session() as session:
        response = session.get(url)
        data = json.loads(response.text)
        return data[tcurr]


def get_yearly_currency_data(fcurr: str, tcurr: str, years: iter) -> iter:
    "bierze statystyki z kazdego dnia na przestrzeni lat"
    limit = 364
    records = [_get_historical_data(fcurr, tcurr, limit, timestamp) for timestamp in years]
    return itertools.chain.from_iterable(records)


def save_data(data: iter):
    session.add_all(data)
    session.commit()


def get_currency_with_models() -> iter:
    "Wyciaga z bazy wszystkie kryptowaluty posiadajace wytrenowane modele"
    return [row.currency for row in session.query(Model).all()]


# Do wypelnienia bazy na poczatku mozna uzyc ponizszych funkcji
def load_sample_models():
    session.add(Model(currency="BTC", long_mean=70, short_mean=30))
    session.add(Model(currency="ETH", long_mean=55, short_mean=20))
    session.commit()


def load_2019_BTC_data():
    timestamp = 1577750400
    limit = 364
    fcurr = "BTC"
    tcurr = "PLN"
    btc_info = _get_historical_data(fcurr, tcurr, limit, timestamp)

    save_data(btc_info)


def get_currency_info(currency):
    records = session.query(Record).filter(Record.currency == currency).order_by(Record.time).all()
    print(records)


def update_model():
    currency = "LTC"
    long_mean = 65
    short_mean = 20
    db_model = session.query(Model).filter(Model.currency == currency).one_or_none()
    if db_model:
        db_model.short_mean = short_mean
        db_model.long_mean = long_mean
    else:
        model = Model(currency=currency, short_mean=short_mean, long_mean=long_mean)
        session.add(model)
    session.commit()
    print(db_model)


if __name__ == '__main__':
    load_sample_models()
    load_2019_BTC_data()

    # get_historical_data(fcurr="BTC", tcurr="PLN", limit=2, timestamp=1554076800)
    # get_yearly_currency_data("BTC", "PLN", YEARS)
    # get_current_data("BTC", "PLN")
    # print(get_currency_with_models())
    # get_currency_info("ETH")
    # update_model()
