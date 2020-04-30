from time import sleep

from spade import agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
from spade.template import Template

from strategy_agent import StrategyAgent
import config


class DecisionAgent(agent.Agent):
    async def setup(self):
        print("Hello World! I'm agent {}".format(str(self.jid)))
        train_template = Template()
        train_template.set_metadata("performative", "inform")
        train_template.set_metadata("ontology", "train")
        self.add_behaviour(self.TrainBehaviour(), train_template)

        list_template = Template()
        list_template.set_metadata("performative", "inform")
        list_template.set_metadata("ontology", "list")
        self.add_behaviour(self.ListBehaviour(), list_template)

        decision_template = Template()
        decision_template.set_metadata("performative", "inform")
        decision_template.set_metadata("ontology", "decision")
        self.add_behaviour(self.DecisionBehaviour(), decision_template)

    class TrainBehaviour(CyclicBehaviour):

        async def run(self):
            message = await self.receive(100)
            if message is not None:
                print(f"train {message.body}")
                strategy_agent_jid = f"{message.body.lower()}@{config.domain}"
                strategy_agent = StrategyAgent(strategy_agent_jid, message.body.lower(), message.body.lower())
                await strategy_agent.start(auto_register=True)
                self.presence.subscribe(strategy_agent_jid)

    class ListBehaviour(CyclicBehaviour):

        async def run(self):
            message = await self.receive(100)
            sleep(5)
            if message is not None:
                print("list")
                message = Message(to="data_agent@127.0.0.1")
                message.set_metadata("performative", "inform")
                message.set_metadata("ontology", "list")
                await self.send(message)

    class DecisionBehaviour(CyclicBehaviour):

        async def run(self):
            message = await self.receive(100)
            sleep(5)
            if message is not None:
                currency = message.body
                print(f"Decision {message.body}")
                message = Message(to="data_agent@127.0.0.1")
                message.set_metadata("performative", "inform")
                message.set_metadata("ontology", "current")
                message.body = currency
                await self.send(message)
