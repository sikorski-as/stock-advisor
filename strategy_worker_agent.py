import asyncio

from spade import agent
from spade.behaviour import CyclicBehaviour
from spade.message import Message
import tools
from protocol import request_cost_computation


class StrategyAgentWorker(agent.Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.log = tools.make_logger(self.jid)

    async def setup(self):
        self.log.debug('Starting!')
        self.add_behaviour(StrategyAgentWorker.MasterConversation(), request_cost_computation)

    class MasterConversation(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(30)  # type: Message
            if msg:
                data = tools.from_json(msg.body)
                reply = msg.make_reply()
                reply.metadata = dict(performative='reply')
                reply.body = tools.to_json([0] * len(data))
                await asyncio.sleep(5)
                self.agent.log.debug('Sending reply!')
                await self.send(reply)


if __name__ == '__main__':
    agent = StrategyAgentWorker('strategy_agent_worker1@localhost', 'strategy_agent_worker1')
    agent.start()
