import asyncio

import jsonpickle
from spade import agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour
from spade.message import Message

import tools
from config import domain
from cost_function import cost_function
from data_agent import DataAgent
from protocol import request_cost_computation, reply_historical_data


class StrategyAgentWorker(agent.Agent):

    def __init__(self, jid, password, currency_symbol, verify_security=False):
        super().__init__(jid, password, verify_security)
        self.currency_symbol = currency_symbol
        self.records_ready = None
        self.records = None
        self.training_records = None
        self.log = tools.make_logger(self.jid)

    async def setup(self):
        self.log.debug('Starting!')
        self.add_behaviour(self.RetrieveDataBehaviour(), reply_historical_data)
        self.add_behaviour(StrategyAgentWorker.MasterConversation(), request_cost_computation)
        self.records_ready = asyncio.Semaphore(value=0)

    class MasterConversation(CyclicBehaviour):
        async def run(self):
            msg = await self.receive(30)  # type: Message
            await self.agent.records_ready.acquire()
            if msg:
                data = jsonpickle.loads(msg.body)
                self.agent.log.debug('Data ready, computing cost function')
                costs = [cost_function(value[0], value[1], self.agent.training_records) for value in data]
                self.agent.log.debug('Cost function computed')
                reply = msg.make_reply()
                reply.metadata = dict(performative='reply')
                reply.body = tools.to_json(costs)
                await asyncio.sleep(5)
                await self.send(reply)
                self.agent.log.debug('Reply sent!')
            self.agent.records_ready.release()

    class RetrieveDataBehaviour(OneShotBehaviour):
        async def run(self):
            self.agent.log.debug('Retrieving data from Data Agent')
            msg = Message(to="data_agent@127.0.0.1")
            msg.set_metadata("performative", "inform")
            msg.set_metadata("ontology", "history")
            msg.body = self.agent.currency_symbol
            await self.send(msg)
            reply = await self.receive(100)
            if reply is not None:
                self.agent.records = jsonpickle.loads(reply.body)
                self.agent.training_records = list(map(lambda x: x.close, sorted(filter(lambda x: x.time > 1514678400, self.agent.records), key=lambda x: x.time)))
                self.agent.records_ready.release()


if __name__ == '__main__':
    data_agent = DataAgent("data_agent@127.0.0.1", "data_agent")
    data_agent.start(auto_register=False)
    agent = StrategyAgentWorker(f'strategy_agent_worker1@{domain}', 'strategy_agent_worker1', "ETH")
    agent.start(auto_register=True)
