from copy import copy

import jsonpickle
from spade import agent
from spade.behaviour import OneShotBehaviour, CyclicBehaviour

import config
import response
import tools
from data_agent import DataAgent
from decision_agent import DecisionAgent


class InterfaceAgent(agent.Agent):
    operations = {
        config.TRAIN_OPERATION: {},
        config.DECISION_OPERATION: {},
        config.LIST_OPERATION: None
    }

    async def main_controller(self, request):
        return {"currencies": [
            {
                "id": 1,
                "name": "BTC"
            },
            {
                "id": 2,
                "name": "LTC"
            },
            {
                "id": 3,
                "name": "ETH"
            }
        ]}

    async def train_controller(self, request):
        print("Train")
        symbol = (await request.post())["symbol"]
        print(symbol)
        resp = self.operations["Train"].get(symbol, None)
        if not resp:
            resp = response.Response()
            self.operations["Train"][symbol] = resp
        train_behaviour = self.RequestTrainBehaviour(symbol)
        self.add_behaviour(train_behaviour)
        return resp.get_json()

    async def decision_controller(self, request):
        print("Decision")
        symbol = (await request.post())["symbol"]
        print(symbol)
        resp = self.operations[config.DECISION_OPERATION].get(symbol, None)
        if not resp:
            resp = response.Response()
            self.operations[config.DECISION_OPERATION][symbol] = resp
            decision_behaviour = self.RequestDecisionBehaviour(symbol)
            self.add_behaviour(decision_behaviour)
            return resp.get_json()
        else:
            prev_resp: response.Response = copy(resp)
            if prev_resp.status == response.Status.DONE:
                resp.status = response.Status.ACTIVE
                decision_behaviour = self.RequestDecisionBehaviour(symbol)
                self.add_behaviour(decision_behaviour)
            return prev_resp.get_json()

    async def list_controller(self, request):
        print("List")
        resp = self.operations[config.LIST_OPERATION]

        if not resp:
            resp = response.Response()
            self.operations[config.LIST_OPERATION] = resp
            request_list_behaviour = self.RequestListBehaviour()
            self.add_behaviour(request_list_behaviour)
            return resp.get_json()
        else:
            prev_resp: response.Response = copy(resp)
            if resp.status == response.Status.DONE:
                resp.status = response.Status.ACTIVE
                request_list_behaviour = self.RequestListBehaviour()
                self.add_behaviour(request_list_behaviour)
            return prev_resp.get_json()

    # async def retrieve_decision_controller(self, request):
    #     symbol = (await request.post())["symbol"]
    #     decision = self.operations[config.DECISION_OPERATION].get(symbol, None)
    #     if decision:
    #         return decision.get_json()
    #     else:
    #         return tools.to_json({"info": f"Nie było prosby o wygenerowanie danych dla {symbol}"})
    #
    # async def retrieve_list_controller(self, request):
    #     if self.operations[config.LIST_OPERATION]:
    #         return self.operations[config.LIST_OPERATION].get_json()
    #     else:
    #         return tools.to_json({"info": "Nie bylo prosby o pobranie listy"})

    async def spawn_agents(self):
        data_agent = DataAgent("data_agent@127.0.0.1", "data_agent")
        await data_agent.start(auto_register=False)
        decision_agent = DecisionAgent("decision_agent@127.0.0.1", "decision_agent")
        await decision_agent.start(auto_register=False)

    async def setup(self):
        print("Hello World! I'm agent {}".format(str(self.jid)))
        self.web.start(port=10000, templates_path="static/templates")
        self.web.add_post("/train", self.train_controller, None)
        self.web.add_post("/decision", self.decision_controller, None)
        self.web.add_get("/list", self.list_controller, None)
        # self.web.add_post("/retrieve/train", self.train_controller, None)
        # self.web.add_post("/retrieve/decision", self.retrieve_decision_controller, None)
        # self.web.add_get("/retrieve/list", self.retrieve_list_controller, None)
        self.web.add_get("", self.main_controller, "main.html")

        decision_template = tools.create_template("inform", "decision")
        self.add_behaviour(self.ResponseDecisionBehaviour(self.operations), decision_template)
        list_template = tools.create_template("inform", "list")
        self.add_behaviour(self.ResponseListBehaviour(self.operations), list_template)

        await self.spawn_agents()

    class RequestTrainBehaviour(OneShotBehaviour):

        def __init__(self, symbol):
            super().__init__()
            self.symbol = symbol

        async def run(self):
            message = tools.create_message("decision_agent@127.0.0.1", "inform", "train", self.symbol)
            await self.send(message)

    class RequestListBehaviour(OneShotBehaviour):
        async def run(self):
            message = tools.create_message("decision_agent@127.0.0.1", "inform", "list", "list")
            await self.send(message)

    class RequestDecisionBehaviour(OneShotBehaviour):

        def __init__(self, symbol):
            super().__init__()
            self.symbol = symbol

        async def run(self):
            message = tools.create_message("decision_agent@127.0.0.1", "inform", "decision", self.symbol)
            await self.send(message)

    class ResponseDecisionBehaviour(CyclicBehaviour):

        def __init__(self, operation_dict: dict):
            super().__init__()
            self.operations = operation_dict

        async def run(self):
            message = await self.receive(config.timeout)
            if message is not None:
                currency, value = jsonpickle.decode(message.body)
                operation = self.operations[config.DECISION_OPERATION][currency]
                operation.body = value
                operation.status = response.Status.DONE
                print(operation)

    class ResponseListBehaviour(CyclicBehaviour):

        def __init__(self, operation_dict: dict):
            super().__init__()
            self.operations = operation_dict

        async def run(self):
            message = await self.receive(config.timeout)
            if message is not None:
                operation = self.operations[config.LIST_OPERATION]
                operation.body = jsonpickle.decode(message.body)
                operation.status = response.Status.DONE
                print(operation)