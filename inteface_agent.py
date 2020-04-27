from spade import agent
from spade.behaviour import OneShotBehaviour
from spade.message import Message

from decision_agent import DecisionAgent


class InterfaceAgent(agent.Agent):
    async def main_controller(self, request):
        return {"ids": [1, 2, 3]}

    async def test_controller(self, request):
        print("Hello, world!")

    async def train_controller(self, request):
        print("Train")
        symbol = (await request.post())["symbol"]
        print(symbol)
        train_behaviour = self.RequestTrainBehaviour(symbol)
        self.add_behaviour(train_behaviour)

    async def decision_controller(self, request):
        print("Decision")

    async def list_controller(self, request):
        print("List")
        request_list_behaviour = self.RequestListBehaviour()
        self.add_behaviour(request_list_behaviour)


    async def spawn_agents(self):
        # data_agent = DataAgent("data_agent@127.0.0.1", "data_agent")
        # await data_agent.start(auto_register=False)
        decision_agent = DecisionAgent("decision_agent@127.0.0.1", "decision_agent")
        await decision_agent.start(auto_register=False)

    async def setup(self):
        print("Hello World! I'm agent {}".format(str(self.jid)))
        self.web.start(port=10000, templates_path="static/templates")
        self.web.add_post("/train", self.train_controller, None)
        self.web.add_get("/decision", self.decision_controller, None)
        self.web.add_get("/list", self.list_controller, None)
        self.web.add_get("", self.main_controller, "main.html")
        self.web.add_get("/test", self.test_controller, None)
        await self.spawn_agents()

    class RequestTrainBehaviour(OneShotBehaviour):

        def __init__(self, symbol):
            super().__init__()
            self.symbol = symbol

        async def run(self):
            message = Message(to="decision_agent@127.0.0.1")
            message.set_metadata("performative", "inform")
            message.set_metadata("ontology", "train")
            message.body = self.symbol
            await self.send(message)

    class RequestListBehaviour(OneShotBehaviour):
        async def run(self):
            message = Message(to="decision_agent@127.0.0.1")
            message.set_metadata("performative", "inform")
            message.set_metadata("ontology", "list")
            message.body = "list"
            await self.send(message)

