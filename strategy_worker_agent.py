from spade import agent


class StrategyAgentWorker(agent.Agent):
    async def setup(self):
        print("Hello World! I'm agent {}".format(str(self.jid)))