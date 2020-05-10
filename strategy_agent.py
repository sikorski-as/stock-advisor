from asyncio import sleep

from aioxmpp import PresenceShow
from spade import agent
from spade.behaviour import OneShotBehaviour, CyclicBehaviour

import config
from tools import make_logger, message_from_template
from protocol import request_decision_template, give_positive_decision_template


class StrategyAgent(agent.Agent):

    def __init__(self, jid, password, currency_symbol, verify_security=False):
        super().__init__(jid, password, verify_security)
        self.currency_symbol = currency_symbol
        self.log = make_logger(self.jid)

    async def setup(self):
        self.log.debug('Starting!')
        self.presence.approve_all = True
        self.add_behaviour(self.TrainBehaviour())

    class TrainBehaviour(OneShotBehaviour):
        async def on_start(self):
            self.presence.set_available(show=PresenceShow.DND)

        async def run(self):
            self.agent.log.debug('Starting training!')
            await sleep(5)
            self.agent.log.debug('Training done!')
            self.agent.add_behaviour(StrategyAgent.GiveDecisionBehaviour(), request_decision_template)

    class GiveDecisionBehaviour(CyclicBehaviour):
        async def on_start(self):
            self.presence.set_available(show=PresenceShow.CHAT)

        async def run(self):
            msg = await self.receive(timeout=config.timeout)
            if msg is not None:
                self.agent.log.debug('I got request_decision_template message!')
                reply = message_from_template(give_positive_decision_template, to=str(msg.sender))
                await self.send(reply)
                self.agent.log.debug('I sent give_positive_decision_template message!')


if __name__ == '__main__':
    agent = StrategyAgent('strategy_agent@localhost', 'strategy_agent', 'BTC')
    agent.start()
