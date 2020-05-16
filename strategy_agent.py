import asyncio
import itertools
import json
import math
import random
from asyncio import sleep

import jsonpickle
import numpy as np
from aioxmpp import PresenceShow
from spade import agent
from spade.behaviour import OneShotBehaviour, CyclicBehaviour
from spade.template import Template

import config
import tools
from data_agent import DataAgent
from tools import make_logger, message_from_template
from protocol import request_decision_template, give_positive_decision_template, request_cost_computation
from strategy_worker_agent import StrategyAgentWorker

from config import domain


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
        await StrategyAgentWorker(f'strategy_agent_worker1@{domain}', 'strategy_agent_worker1', self.currency_symbol).start(auto_register=True)
        await StrategyAgentWorker(f'strategy_agent_worker2@{domain}', 'strategy_agent_worker2', self.currency_symbol).start(auto_register=True)

    class TrainBehaviour(OneShotBehaviour):
        def __init__(self, *args, **kwargs):
            super(StrategyAgent.TrainBehaviour, self).__init__()
            self.computed_cost_function = []
            self.computed_cost_function_arrived = asyncio.Semaphore(value=0)
            self.workers = [
                f'strategy_agent_worker1@{domain}',
                f'strategy_agent_worker2@{domain}',
            ]

        async def on_start(self):
            self.presence.set_available(show=PresenceShow.DND)

        async def run(self):
            self.agent.log.debug('Starting training!')

            population_size = 6
            mutation_chance = 0.05
            niterations = 20
            random_genotype = lambda: np.array([np.random.randint(10, 30), np.random.randint(100, 300)])
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
                print(costs)
                population = [genotype for (genotype, cost) in sorted(zip(population, costs), key=lambda x: x[1])]
                population = population[:population_size]

            self.agent.log.debug('Training done!')
            self.agent.add_behaviour(StrategyAgent.GiveDecisionBehaviour(), request_decision_template)

        async def compute_cost_function(self, population):
            chunks = tools.split_into_chunks(population, len(self.workers))
            not_empty_chunks = filter(None, chunks)
            waits = 0

            for i, chunk in enumerate(not_empty_chunks):
                if chunk:
                    worker = self.workers[i]
                    worker_conversation = StrategyAgent.WorkerConversationBehaviour(worker, i, chunk)
                    self.agent.add_behaviour(worker_conversation)
                    waits += 1

            self.computed_cost_function = [None] * waits

            for i in range(waits):
                await self.computed_cost_function_arrived.acquire()

            return list(itertools.chain(self.computed_cost_function))

        async def feed_computed_cost_function(self, data_range_id, data):
            self.computed_cost_function[data_range_id] = data
            self.computed_cost_function_arrived.release()

    class WorkerConversationBehaviour(OneShotBehaviour):
        ATTEMPTS = 2

        def __init__(self, worker_jid, data_range_id, data, *args, **kwargs):
            super(StrategyAgent.WorkerConversationBehaviour, self).__init__()
            self.data_range_id = data_range_id
            self.data = data
            self.worker_jid = worker_jid
            self.conversation_id = tools.make_uuid()
            self.set_template(Template(thread=self.conversation_id))

        async def on_start(self):
            pass

        async def run(self):
            for _ in range(self.ATTEMPTS):
                msg = message_from_template(request_cost_computation,
                                            body=jsonpickle.dumps(self.data),
                                            to=self.worker_jid,
                                            thread=self.conversation_id)
                await self.send(msg)
                reply = await self.receive(30)
                if reply:
                    self.agent.log.debug('Reply from worker {} arrived!'.format(self.worker_jid))
                    computed_data = tools.from_json(reply.body)
                    print(computed_data)
                    await self.agent.training_behaviour.feed_computed_cost_function(self.data_range_id, computed_data)
                    break
            else:
                self.agent.log.error('Reply from worker {} not arrived!'.format(self.worker_jid))
                # todo: dodanie obsługi awarii
                return

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
    data_agent = DataAgent("data_agent@127.0.0.1", "data_agent")
    data_agent.start(auto_register=False)
    agent = StrategyAgent(f'strategy_agent@{domain}', 'strategy_agent', 'BTC')
    agent.start(auto_register=True)
