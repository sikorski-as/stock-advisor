from time import sleep

from aioxmpp import PresenceShow
from spade import agent
from spade.behaviour import OneShotBehaviour, CyclicBehaviour
from spade.template import Template


class StrategyAgent(agent.Agent):

    def __init__(self, jid, password, currency_symbol, verify_security=False):
        super().__init__(jid, password, verify_security)
        self.currency_symbol = currency_symbol

    async def setup(self):
        print("Hello World! I'm agent {}".format(str(self.jid)))
        self.presence.approve_all = True
        train_behaviour = self.TrainBehaviour()
        self.add_behaviour(train_behaviour)

    class TrainBehaviour(OneShotBehaviour):
        async def on_start(self):
            self.presence.set_available(show=PresenceShow.DND)

        async def run(self):
            print("train")
            sleep(30)
            print("train done")
            give_decision_behaviour = StrategyAgent.GiveDecisionBehaviour()
            give_decision_template = Template()
            give_decision_template.set_metadata("performative", "request")
            give_decision_template.set_metadata("ontology", "give_decision")
            self.agent.add_behaviour(give_decision_behaviour, give_decision_behaviour)

    class GiveDecisionBehaviour(CyclicBehaviour):
        async def on_start(self):
            self.presence.set_available(show=PresenceShow.CHAT)

        async def run(self):
            message = await self.receive(100)
            if message is not None:
                print("decision")
