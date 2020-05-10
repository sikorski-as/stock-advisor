import asyncio
import itertools
import json

import jsonpickle as jsonpickle
from aiohttp import ClientConnectorError

import config

from spade import agent
from spade.behaviour import OneShotBehaviour, CyclicBehaviour
import tools
from database import builder
from database.models import Model, Record
import aiohttp


class DataAgent(agent.Agent):

    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.session = builder.Session()

    async def setup(self):

        print("Hello World! I'm agent {}".format(str(self.jid)))

        history_data_template = tools.create_template("inform", "history")
        self.add_behaviour(self.HistoryDataBehaviour(self.session), history_data_template)

        current_data_template = tools.create_template("inform", "current")
        self.add_behaviour(self.CurrentDataBehaviour(self.session), current_data_template)

        list_models_template = tools.create_template("inform", "list")
        self.add_behaviour(self.ListModelsBehaviour(self.session), list_models_template)

        get_model_template = tools.create_template("inform", "getModel")
        self.add_behaviour(self.GetModelBehaviour(self.session), get_model_template)

        save_model_template = tools.create_template("inform", "saveModel")
        self.add_behaviour(self.SaveModelBehaviour(self.session), save_model_template)

    class HistoryDataBehaviour(CyclicBehaviour):
        "Epoch time dla lat 2014-2019, gdzie pierwszy element to 31.12.2014"
        YEARS = [1419984000, 1451520000, 1483142400, 1514678400, 1546214400, 1577750400]

        def __init__(self, session):
            super().__init__()
            self.session = session

        async def run(self):
            message = await self.receive(config.timeout)
            if message is not None:
                currency = message.body
                print(f"Wczytuje dane historyczne dla {currency}")
                records = list(await self._get_yearly_currency_data(currency, "PLN", self.YEARS))
                if not records:
                    records = self._get_info_from_db(currency).all()
                    if not records:
                        print("Polaczenie z siecia zawiodlo i nie ma tez zadnego backupu w bazie")
                    else:
                        print(f"Sa dane w bazie do wykorzystania")
                print(f"Pobrano {len(records)} wyników dla {currency}")
                print(records[::25])

        def _create_records(self, currency: str, info: iter):
            return [Record(currency=currency, time=time, high=high, low=low, open=open, close=close)
                    for time, high, low, open, close in info]

        def _retrieve_information(self, data: dict):
            general_info = data['Data']
            list_of_records = general_info['Data']
            attrs = ["time", "high", "low", "open", "close"]
            return [[record_info[attr] for attr in attrs] for record_info in list_of_records]

        async def _get_historical_data(self, session, fcurr: str, tcurr: str, limit: int, timestamp: int = None):
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
            try:
                async with session.get(url) as response:
                    data = json.loads(await response.text())
                    info = self._retrieve_information(data)
                    return self._create_records(fcurr, info)
            except ClientConnectorError as e:
                print("Brak połączenia z siecią!")
                return []

        async def _get_yearly_currency_data(self, fcurr: str, tcurr: str, years: iter) -> iter:
            "bierze statystyki z kazdego dnia na przestrzeni lat"
            limit = 364
            async with aiohttp.ClientSession() as session:
                tasks = [self._get_historical_data(session, fcurr, tcurr, limit, timestamp) for timestamp in years]
                records = await asyncio.gather(*tasks)
                return itertools.chain.from_iterable(records)

        def _get_info_from_db(self, currency):
            return self.session.query(Record).filter(Record.currency == currency).order_by(Record.time)

    class CurrentDataBehaviour(CyclicBehaviour):
        def __init__(self, session):
            super().__init__()
            self.session = session

        async def run(self):
            message = await self.receive(config.timeout)
            if message is not None:
                currency = message.body
                print(f"Wczytuje aktualny kurs dla {currency}")
                value = await self._get_value(currency)
                print(f"Aktualny kurs to {value}")
                message = tools.create_message("interface_agent@127.0.0.1", "inform", "decision",
                                               jsonpickle.encode((currency, value)))
                await self.send(message)

        async def _get_value(self, fcurr, tcurr="PLN"):
            "Pobiera aktualny kurs waluty"
            url = f"https://min-api.cryptocompare.com/data/price?fsym={fcurr}&tsyms={tcurr}"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        data = json.loads(await response.text())
                        return data[tcurr]
            except ClientConnectorError as e:
                print("Nie ma polaczenia z siecia!")

    class ListModelsBehaviour(CyclicBehaviour):

        def __init__(self, session):
            super().__init__()
            self.session = session

        async def run(self):
            message = await self.receive(10)
            if message is not None:
                models_available = self._get_currency_with_models()
                print(f"Dostępne modele to: {models_available}")
                message = tools.create_message("interface_agent@127.0.0.1", "inform", "list",
                                               jsonpickle.encode(models_available))
                await self.send(message)

        def _get_currency_with_models(self) -> iter:
            "Wyciaga z bazy wszystkie kryptowaluty posiadajace wytrenowane modele"
            return [row.currency for row in self.session.query(Model).all()]

    class GetModelBehaviour(CyclicBehaviour):
        """
            Message body should contain name of currency
            Example message.body = "BTC"
        """

        def __init__(self, session):
            super().__init__()
            self.session = session

        async def run(self):
            message = await self.receive(10)
            if message is not None:
                currency = message.body
                model = self.session.query(Model).filter(Model.currency == currency).one_or_none()
                print(f"Model dla waluty {currency} to {model.short_mean, model.long_mean}")

    class SaveModelBehaviour(CyclicBehaviour):
        """
            Message body should contain name and short_mean and long_mean
            Example model = {
                "currency": "BTC",
                "short_mean": 20,
                "long_mean": 50
            }
            message.body = tools.to_json(model)
        """

        def __init__(self, session):
            super().__init__()
            self.session = session

        async def run(self):
            message = await self.receive(10)
            if message is not None:
                model_info = tools.from_json(message.body)
                self.save_model(**model_info)
                print(f"Zapisano model {model_info['currency']}")

        def save_model(self, currency, short_mean, long_mean):
            db_model = self.session.query(Model).filter(Model.currency == currency).one_or_none()
            if db_model:
                db_model.short_mean = short_mean
                db_model.long_mean = long_mean
            else:
                model = Model(currency=currency, short_mean=short_mean, long_mean=long_mean)
                self.session.add(model)
            self.session.commit()
