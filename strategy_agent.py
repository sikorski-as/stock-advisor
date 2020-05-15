import asyncio
import itertools
from collections import namedtuple
from copy import deepcopy

import numpy as np
from aioxmpp import PresenceShow
from spade import agent
from spade.behaviour import OneShotBehaviour, CyclicBehaviour
from spade.template import Template

import config
import tools
from protocol import request_decision_template, give_positive_decision_template, request_cost_computation, \
    give_negative_decision_template
from strategy_worker_agent import StrategyAgentWorker
from tools import make_logger, message_from_template

Job = namedtuple('Job', 'job_id worker_id data result')
WorkerDescriptor = namedtuple('WorkerDescriptor', 'status assigned_jobs')


class JobManager:
    SAFE_MODE = True  # data is deep-copied

    def __init__(self, workers=None):
        self._workers = {worker_id: WorkerDescriptor(True, 0) for worker_id in workers} if workers is not None else {}
        self._jobs = []
        self._jobs_done = None

    def _reset(self):
        self._workers = {worker_id: WorkerDescriptor(True, 0) for worker_id in self._workers}
        self._jobs = []
        self._jobs_done = None

    def _reset_workers_status(self):
        for worker_id in self._workers:
            self._workers[worker_id].status = True

    def _available_workers(self):
        workers = [worker_id for worker_id, descriptor in self._workers if descriptor.status]
        if workers:
            return workers
        else:
            self._reset_workers_status()
            return list(self._workers.keys())

    def _get_one_worker(self):
        available_workers = self._available_workers()
        worker, jobs = min(self._workers.items(),
                           key=lambda worker_and_descriptor: worker_and_descriptor[1].assigned_jobs)
        self._workers[worker] += 1
        return worker

    def create_jobs(self, data: list, max_jobs: int = None):
        if self._jobs:
            raise Exception('Cannot create jobs, jobs already created')

        workers = self._available_workers()
        nworkers = len(workers)
        max_jobs = nworkers if max_jobs is None else max_jobs
        njobs = min(max(max_jobs, 1), nworkers)
        chunks = tools.split_into_chunks(data, njobs)
        not_empty_chunks = filter(None, chunks)

        for i, chunk in enumerate(not_empty_chunks):
            worker = self._get_one_worker()
            job = Job(i, worker, data=chunk, result=None)
            self._jobs.append(job)

        if self._jobs_done is None:
            self._jobs_done = asyncio.Semaphore(value=0)

        return deepcopy(self._jobs)

    def job_done(self, job: Job):
        if not self._jobs:
            raise Exception('Jobs not created!')

        self._jobs[job.job_id] = job
        self._workers[job.worker_id].assigned_jobs -= 1
        self._workers[job.worker_id].status = True

    def job_failed(self, job: Job):
        if not self._jobs:
            raise Exception('Jobs not created!')

        if job.worker_id not in self._workers:
            msg = 'Worker {} not found in JobManager (was worker_id of a job modified?)'.format(job.worker_id)
            raise ValueError(msg)
        self._workers[job.worker_id].assigned_jobs -= 1
        self._workers[job.worker_id].status = False
        new_worker = self._get_one_worker()
        self._jobs[job.job_id].worker_id = new_worker

    async def jobs_finished(self):
        if not self._jobs:
            raise Exception('Jobs not created!')

        for _ in range(len(self._jobs)):
            await self._jobs_done

        results = list(itertools.chain(job.result for job in self._jobs))
        self._reset()

        return results


class StrategyAgent(agent.Agent):
    def __init__(self, jid, password, currency_symbol, verify_security=False):
        super().__init__(jid, password, verify_security)
        self.currency_symbol = currency_symbol
        self.log = make_logger(self.jid)
        self.training_behaviour = None
        self.has_strategy = False

    async def setup(self):
        self.log.debug('Starting!')
        await StrategyAgentWorker('strategy_agent_worker1@localhost', 'strategy_agent_worker1').start()
        await StrategyAgentWorker('strategy_agent_worker2@localhost', 'strategy_agent_worker2').start()
        self.presence.subscribe('strategy_agent_worker1@localhost')
        self.presence.subscribe('strategy_agent_worker2@localhost')
        await asyncio.sleep(10)
        self.training_behaviour = self.TrainBehaviour()
        self.add_behaviour(self.training_behaviour)
        self.add_behaviour(StrategyAgent.GiveDecisionBehaviour(), request_decision_template)

    @property
    def available_workers(self):
        contacts = self.presence.get_contacts()
        available_workers = []
        for jid, contact in contacts.items():
            sjid = str(jid)
            if 'strategy_agent_worker' in sjid:
                available_workers.append(sjid)
        return available_workers

    class TrainBehaviour(OneShotBehaviour):
        def __init__(self, *args, **kwargs):
            super(StrategyAgent.TrainBehaviour, self).__init__()
            self.computed_cost_function = []
            self.computed_cost_function_arrived = asyncio.Semaphore(value=0)

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

        async def compute_cost_function(self, population):
            workers = self.agent.available_workers
            chunks = tools.split_into_chunks(population, len(workers))
            not_empty_chunks = filter(None, chunks)
            waits = 0

            for i, chunk in enumerate(not_empty_chunks):
                if chunk:
                    worker = workers[i]
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
                                            body=tools.to_json(self.data),
                                            to=self.worker_jid,
                                            thread=self.conversation_id)
                await self.send(msg)
                reply = await self.receive(30)
                if reply:
                    self.agent.log.debug('Reply from worker {} arrived!'.format(self.worker_jid))
                    computed_data = tools.from_json(reply.body)
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
    agent = StrategyAgent('strategy_agent@localhost', 'strategy_agent', 'BTC')
    agent.start()
