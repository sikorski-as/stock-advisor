import asyncio
import math
import random
from asyncio import sleep

import numpy as np
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
        self.training_behaviour = None

    async def setup(self):
        self.log.debug('Starting!')
        self.presence.approve_all = True
        self.training_behaviour = self.TrainBehaviour()
        self.add_behaviour(self.training_behaviour)

    class TrainBehaviour(OneShotBehaviour):
        def __init__(self, *args, **kwargs):
            super(StrategyAgent.TrainBehaviour, self).__init__()
            self.cost_functions_ready = asyncio.Event()
            self.cost_functions = {}
            self.workers = [
                'strategy_agent_worker@localhost'
            ]

        async def on_start(self):
            self.presence.set_available(show=PresenceShow.DND)

        async def run(self):
            self.agent.log.debug('Starting training!')

            population_size = 6
            mutation_chance = 0.05
            niterations = 20
            random_genotype = lambda: np.random.randint(1, 6, size=(2,))
            repair = lambda genes: np.where(genes < 1, 1, genes)
            _mutate = lambda genes: genes + np.random.randint(-1, 2, size=(2,))
            mutate = lambda genes: repair(_mutate(genes))

            population = [random_genotype() for _ in range(population_size)]
            for i in range(niterations):
                self.agent.log.debug(f'Starting iteration {i}')
                population.extend([
                    mutate(genotype) if np.random.random() > mutation_chance
                    else genotype
                    for genotype in population
                ])
                costs = await self.compute_cost_function(population)
                population = [genotype for (genotype, cost) in sorted(zip(population, costs), key=lambda x: x[1])]
                population = population[:population_size]

            self.agent.log.debug('Training done!')
            self.agent.add_behaviour(StrategyAgent.GiveDecisionBehaviour(), request_decision_template)

        async def compute_cost_function(self, population):
            return [0 for _ in population]

    class WorkerConversationBehaviour(OneShotBehaviour):
        async def on_start(self):
            pass

        async def run(self):
            pass

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
