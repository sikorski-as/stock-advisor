from time import sleep

from spade import agent
from spade.behaviour import CyclicBehaviour

import tools
from strategy_agent import StrategyAgent
import config


class DecisionAgent(agent.Agent):
    async def setup(self):
        print("Hello World! I'm agent {}".format(str(self.jid)))
        train_template = tools.create_template("inform", "train")
        self.add_behaviour(self.TrainBehaviour(), train_template)

        list_template = tools.create_template("inform", "list")
        self.add_behaviour(self.ListBehaviour(), list_template)

        decision_template = tools.create_template("inform", "decision")
        self.add_behaviour(self.DecisionBehaviour(), decision_template)

    class TrainBehaviour(CyclicBehaviour):

        async def run(self):
            message = await self.receive(config.timeout)
            if message is not None:
                print(f"train {message.body}")
                strategy_agent_jid = f"{message.body.lower()}@{config.domain}"
                strategy_agent = StrategyAgent(strategy_agent_jid, message.body.lower(), message.body.lower())
                await strategy_agent.start(auto_register=True)
                self.presence.subscribe(strategy_agent_jid)

    class ListBehaviour(CyclicBehaviour):

        async def run(self):
            message = await self.receive(config.timeout)
            if message is not None:
                print("list")
                message = tools.create_message("data_agent@127.0.0.1", "inform", "list", "")
                await self.send(message)

    class DecisionBehaviour(CyclicBehaviour):

        async def run(self):
            message = await self.receive(config.timeout)
            sleep(5)
            if message is not None:
                currency = message.body
                print(f"Decision {message.body}")
                message = tools.create_message("data_agent@127.0.0.1", "inform", "current", currency)
                await self.send(message)


if __name__ == '__main__':
    agent = DecisionAgent('decision_agent@localhost', 'decision_agent')
    agent.start()
