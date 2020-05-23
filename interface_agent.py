import jsonpickle
from spade import agent
from spade.behaviour import OneShotBehaviour, CyclicBehaviour

import config
import response
import tools
from data_agent import DataAgent
from decision_agent import DecisionAgent


class InterfaceAgent(agent.Agent):

    def __init__(self, jid, passwd):
        super().__init__(jid, passwd)
        self.log = tools.make_logger(self.jid)
        self.receiver = None

    async def hello(self, websocket, path):
        self.receiver = websocket
        async for message in websocket:
            request = jsonpickle.decode(message)
            if request['action'] == 'list':
                resp = await self.list_handler()
            elif request['action'] == 'decision':
                symbol = str.lower(request['body'])
                resp = await self.decision_handler(symbol)
            elif request['action'] == 'train':
                symbol = str.lower(request['body'])
                resp = await self.train_handler(symbol)
            else:
                resp = response.Response()
                resp.body = 'Bad request'
                resp.status = response.Status.FAIL
            await websocket.send(resp.get_json())

    async def list_handler(self):
        resp = response.Response.basic_response()
        resp.type = response.Type.LIST
        request_list_behaviour = self.RequestListBehaviour()
        self.add_behaviour(request_list_behaviour)
        return resp

    async def decision_handler(self, symbol):
        resp = response.Response.basic_response()
        resp.type = response.Type.DECISION
        decision_behaviour = self.RequestDecisionBehaviour(symbol)
        self.add_behaviour(decision_behaviour)
        return resp

    async def train_handler(self, symbol):
        resp = response.Response.basic_response()
        resp.type = response.Type.TRAIN
        train_behaviour = self.RequestTrainBehaviour(symbol)
        self.add_behaviour(train_behaviour)
        return resp

    async def main_controller(self, request):
        return {}

    async def spawn_agents(self):
        data_agent = DataAgent("data_agent@127.0.0.1", "data_agent")
        await data_agent.start(auto_register=False)
        decision_agent = DecisionAgent("decision_agent@127.0.0.1", "decision_agent")
        await decision_agent.start(auto_register=False)

    async def setup(self):
        self.log.debug("Hello World! I'm agent {}".format(str(self.jid)))
        self.web.start(port=10000, templates_path="static/templates")
        self.web.add_get("", self.main_controller, "main.html")

        decision_template = tools.create_template("inform", "decision")
        self.add_behaviour(self.ResponseDecisionBehaviour(), decision_template)
        list_template = tools.create_template("inform", "list")
        self.add_behaviour(self.ResponseListBehaviour(), list_template)
        train_template = tools.create_template("inform", "train")
        self.add_behaviour(self.ResponseTrainBehaviour(), train_template)

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
            message = tools.create_message("decision_agent@127.0.0.1", "request", "list", "list")
            await self.send(message)

    class RequestDecisionBehaviour(OneShotBehaviour):
        def __init__(self, symbol):
            super().__init__()
            self.symbol = symbol

        async def run(self):
            message = tools.create_message("decision_agent@127.0.0.1", "request", "decision", self.symbol)
            await self.send(message)

    class ResponseDecisionBehaviour(CyclicBehaviour):
        def __init__(self):
            super().__init__()

        async def run(self):
            message = await self.receive(config.timeout)
            if message is not None:
                self.agent.log.debug('Got decision from decision agent!')
                currency, value = jsonpickle.decode(message.body)
                resp = response.Response()
                if not value:
                    resp.status = response.Status.FAIL
                    resp.body = f'Could not get decision for {currency}'
                else:
                    resp.status = response.Status.DONE
                    resp.body = f"{currency} - {value}"
                resp.type = response.Type.DECISION
                self.agent.log.debug(resp)
                await self.agent.receiver.send(resp.get_json())

    class ResponseListBehaviour(CyclicBehaviour):

        def __init__(self):
            super().__init__()

        async def run(self):
            message = await self.receive(config.timeout)
            if message is not None:
                resp = response.Response()
                resp.body = jsonpickle.decode(message.body)
                resp.status = response.Status.DONE
                resp.type = response.Type.LIST
                self.agent.log.debug(resp)
                await self.agent.receiver.send(resp.get_json())

    class ResponseTrainBehaviour(CyclicBehaviour):

        def __init__(self):
            super().__init__()

        async def run(self):
            message = await self.receive(config.timeout)
            if message is not None:
                currency, model = jsonpickle.decode(message.body)
                resp = response.Response()
                if not model:
                    resp.status = response.Status.FAIL
                    resp.body = f'Could not get model for {currency}'
                else:
                    resp.status = response.Status.DONE
                    resp.body = f"{currency} - {model}"
                resp.type = response.Type.TRAIN
                self.agent.log.debug(resp)
                await self.agent.receiver.send(resp.get_json())
