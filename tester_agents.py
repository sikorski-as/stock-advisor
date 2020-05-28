import logging

from spade import quit_spade
from spade.agent import Agent
from spade.behaviour import OneShotBehaviour

import config
import tools
from protocol import request_decision_template


class TestAgent(Agent):
    def __init__(self, *args, **kwargs):
        super(TestAgent, self).__init__(*args, **kwargs)
        self.log = tools.make_logger(self.jid, level=logging.DEBUG)

    async def setup(self):
        self.add_behaviour(TestAgent.TestMessage())

    class TestMessage(OneShotBehaviour):
        async def run(self):
            self.agent.log.debug('Sending message...')
            msg = tools.message_from_template(request_decision_template, to=f'strategy_agent@{config.domain}')
            await self.send(msg)
            self.agent.log.debug('Message sent!')
            reply = await self.receive(timeout=5)
            if reply:
                self.agent.log.debug('Answer received!')
            else:
                self.agent.log.debug('Answer not received! :(')

            quit_spade()

        async def on_end(self):
            self.agent.log.debug('Stopping behaviour')

    async def on_end(self):
        self.log.debug('Stopping agent')


if __name__ == '__main__':
    tester = TestAgent(f'tester@{config.domain}', 'tester')
    tester.start()
