from time import sleep

from spade import agent
from spade.behaviour import CyclicBehaviour
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
