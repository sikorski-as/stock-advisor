import jsonpickle
import numpy as np
from aioxmpp import PresenceShow
from spade import agent
from spade.behaviour import OneShotBehaviour, CyclicBehaviour
from spade.template import Template

import config
import tools
from config import domain
from data_agent import DataAgent
from job_manager import JobManager
from protocol import give_negative_decision_template
from protocol import request_decision_template, give_positive_decision_template, request_cost_computation
from strategy_worker_agent import StrategyAgentWorker
from tools import make_logger, message_from_template


class StrategyAgent(agent.Agent):
    def __init__(self, jid, password, currency_symbol, verify_security=False):
        super().__init__(jid, password, verify_security)
        self.currency_symbol = currency_symbol
        self.log = make_logger(self.jid)
        self.training_behaviour = None
        self.has_strategy = False

    async def setup(self):
        self.log.debug('Starting!')
        await StrategyAgentWorker(f'strategy_agent_worker1@{domain}', 'strategy_agent_worker1', self.currency_symbol).start(auto_register=True)
        await StrategyAgentWorker(f'strategy_agent_worker2@{domain}', 'strategy_agent_worker2', self.currency_symbol).start(auto_register=True)
        self.training_behaviour = self.TrainBehaviour()
        self.add_behaviour(self.training_behaviour)
        self.add_behaviour(StrategyAgent.GiveDecisionBehaviour(), request_decision_template)

    class TrainBehaviour(OneShotBehaviour):
        def __init__(self, *args, **kwargs):
            super(StrategyAgent.TrainBehaviour, self).__init__()
            self.job_manager = JobManager(
                workers=[f'strategy_agent_worker1@{domain}', f'strategy_agent_worker2@{domain}'])

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
                costs = await self.compute_costs(population)
                population = [genotype for (genotype, cost) in sorted(zip(population, costs), key=lambda x: x[1])]
                population = population[:population_size]

            self.agent.log.debug('Training done!')

        async def compute_costs(self, population):
            jobs = await self.job_manager.create_jobs(data=population)
            for job in jobs:
                uuid = tools.make_uuid()
                template = Template(thread=uuid)
                self.agent.add_behaviour(StrategyAgent.WorkerConversationBehaviour(job, uuid), template)

            return await self.job_manager.jobs_finished()

    class WorkerConversationBehaviour(OneShotBehaviour):
        ATTEMPTS = 2

        def __init__(self, job, uuid, *args, **kwargs):
            super(StrategyAgent.WorkerConversationBehaviour, self).__init__()
            self.job = job
            self.conversation_id = uuid

        async def on_start(self):
            pass

        async def run(self):
            while True:
                for attempt in range(self.ATTEMPTS):
                    msg = message_from_template(request_cost_computation,
                                                body=jsonpickle.dumps(self.job.data),
                                                to=self.job.worker_id,
                                                thread=self.conversation_id)
                    await self.send(msg)
                    reply = await self.receive(20)
                    if reply:
                        self.job.result = jsonpickle.loads(reply.body)
                        self.agent.log.debug('Reply from worker {} arrived: {}'.format(reply.sender, self.job.result))
                        await self.agent.training_behaviour.job_manager.job_done(self.job)
                        return
                else:
                    self.agent.log.error('Reply from worker {} not arrived!'.format(self.job.worker_id))
                    self.job = await self.agent.training_behaviour.job_manager.job_failed(self.job)

    class GiveDecisionBehaviour(CyclicBehaviour):
        async def on_start(self):
            self.presence.set_available(show=PresenceShow.CHAT)

        async def run(self):
            msg = await self.receive(timeout=config.timeout)
            if msg is not None:
                self.agent.log.debug('I got request_decision_template message!')
                if self.agent.has_strategy:
                    # jest wytrenowany model, odsyłamy decyzję
                    reply = message_from_template(give_positive_decision_template, to=str(msg.sender))
                    await self.send(reply)
                    self.agent.log.debug('I sent give_positive_decision_template message!')
                else:
                    # trwa trening, nie można dać decyzji
                    reply = message_from_template(give_negative_decision_template, to=str(msg.sender))
                    await self.send(reply)
                    self.agent.log.debug('I sent give_negative_decision_template message!')


if __name__ == '__main__':
    data_agent = DataAgent(f"data_agent@{domain}", "data_agent")
    data_agent.start(auto_register=False)
    agent = StrategyAgent(f'strategy_agent@{domain}', 'strategy_agent', 'BTC')
    agent.start(auto_register=True)
