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

from protocol import request_model_from_db_template, save_model_to_db_template


class DataAgent(agent.Agent):

    def __init__(self, jid, password):
        super().__init__(jid, password)
        self.session = builder.Session()
        self.log = tools.make_logger(self.jid)

    async def setup(self):

        self.log.debug("Hello World! I'm agent {}".format(str(self.jid)))

        history_data_template = tools.create_template("inform", "history")
        self.add_behaviour(self.HistoryDataBehaviour(self.session), history_data_template)

        current_data_template = tools.create_template("inform", "current")
        self.add_behaviour(self.CurrentDataBehaviour(self.session), current_data_template)

        list_models_template = tools.create_template("request", "list")
        self.add_behaviour(self.ListModelsBehaviour(self.session), list_models_template)

        self.add_behaviour(self.GetModelBehaviour(self.session), request_model_from_db_template)

        self.add_behaviour(self.SaveModelBehaviour(self.session), save_model_to_db_template)

    class HistoryDataBehaviour(CyclicBehaviour):
        "Epoch time dla lat 2014-2019, gdzie pierwszy element to 31.12.2014"
        YEARS = [1419984000, 1451520000, 1483142400, 1514678400, 1546214400, 1577750400]

        def __init__(self, session):
            super().__init__()
            self.session = session

        async def run(self):
            message = await self.receive(config.timeout)
            if message is not None:
                currency, days_amount = jsonpickle.decode(message.body)

                if not days_amount:
                    self.agent.log.debug(f"Wczytuje dane historyczne dla {currency}")
                    records = list(await self._get_yearly_currency_data(currency, "PLN", self.YEARS))
                    if not records:
                        records = self._get_info_from_db(currency).all()
                        if not records:
                            self.agent.log.debug(
                                "Polaczenie z siecia zawiodlo i nie ma tez zadnego backupu w bazie lub dana waluta nie istnieje")
                        else:
                            self.agent.log.debug(f"Sa dane w bazie do wykorzystania")
                else:
                    self.agent.log.debug(f"Wczytuje informacje z ostatnich {days_amount} dni dla {currency}")
                    records = await self._get_last_days_currency_data(currency, "PLN", days_amount)

                self.agent.log.debug(f"Pobrano {len(records)} wyników dla {currency}")
                reply = message.make_reply()
                reply.set_metadata("performative", "reply")
                reply.set_metadata("what", "historical data")
                reply.body = jsonpickle.dumps(records)
                await self.send(reply)
                print(records[::25])

        def _create_records(self, currency: str, info: iter):
            return [Record(currency=currency, time=time, high=high, low=low, open=open, close=close)
                    for time, high, low, open, close in info]

        def _retrieve_information(self, data: dict):
            general_info = data.get('Data')
            if general_info:
                list_of_records = general_info['Data']
                attrs = ["time", "high", "low", "open", "close"]
                return [[record_info[attr] for attr in attrs] for record_info in list_of_records]
            else:
                return []

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
            # print(url)
            try:
                async with session.get(url) as response:
                    data = json.loads(await response.text())
                    info = self._retrieve_information(data)
                    if info:
                        return self._create_records(fcurr, info)
                    else:
                        return []
            except ClientConnectorError as e:
                self.agent.log.debug("Brak połączenia z siecią!")
                return []

        async def _get_last_days_currency_data(self, fcurr: str, tcurr: str, n: int):
            async with aiohttp.ClientSession() as session:
                # przy podaniu n api zwraca n+1 wyników stąd n-1
                records = await self._get_historical_data(session, fcurr, tcurr, n-1)
                # print(records)
                return records

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
                self.agent.log.debug(f"Wczytuje aktualny kurs dla {currency}")
                value = await self._get_value(currency)
                self.agent.log.debug(f"Aktualny kurs to {value}")
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
                        return data.get(tcurr)
            except ClientConnectorError as e:
                self.agent.log.debug("Nie ma polaczenia z siecia!")
                return None

    class ListModelsBehaviour(CyclicBehaviour):

        def __init__(self, session):
            super().__init__()
            self.session = session

        async def run(self):
            message = await self.receive(10)
            if message is not None:
                models_available = self._get_currency_with_models()
                self.agent.log.debug(f"Dostępne modele to: {models_available}")
                message = tools.create_message(str(message.sender), "inform", "list",
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
                reply = message.make_reply()
                reply.set_metadata("performative", "reply")
                reply.set_metadata("what", "model")
                if model:
                    reply.body = jsonpickle.dumps(model)
                    self.agent.log.debug(f"Model dla waluty {currency} to {model.short_mean, model.long_mean}")
                    await self.send(reply)
                else:
                    reply.body = jsonpickle.dumps(None)
                    self.agent.log.debug(f"Nie ma modelu dla {currency}")
                    await self.send(reply)

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
                model = jsonpickle.loads(message.body)
                self.save_model(model)
                self.agent.log.debug(f"Zapisano model {model.currency}")

        def save_model(self, model):
            db_model = self.session.query(Model).filter(Model.currency == model.currency).one_or_none()
            if db_model:
                db_model.short_mean = model.short_mean
                db_model.long_mean = model.long_mean
            else:
                m = Model(currency=model.currency, long_mean=int(model.long_mean), short_mean=int(model.short_mean))
                self.session.add(m)
            self.session.commit()
