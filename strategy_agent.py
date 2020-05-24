import asyncio

import jsonpickle
import numpy as np
from aioxmpp import PresenceShow
from spade import agent
from spade.behaviour import OneShotBehaviour, CyclicBehaviour
from spade.template import Template

import config
import protocol
import tools
from config import domain
from data_agent import DataAgent
from database.models import Model
from decision import decision
from job_manager import JobManager
from protocol import give_negative_decision_template, request_model_from_db_template, give_model_template, \
    save_model_to_db_template, give_data_template, reply_historical_data, give_decision_not_available_template
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
        self.model = None
        self.decision_records = None
        self.startup_done = False

    async def setup(self):
        self.log.debug('Starting!')
        self.training_behaviour = self.TrainBehaviour()
        self.add_behaviour(self.PrepareModelBehaviour(), give_model_template)
        self.add_behaviour(self.PrepareDataBehaviour(), reply_historical_data)
        self.add_behaviour(self.TrainingRequestBehaviour(), protocol.request_train_template)

    def prepare_model_ready_message(self):
        m = self.model
        model_info = jsonpickle.encode((self.currency_symbol, (m.short_mean, m.long_mean)))
        model_ready_msg = tools.message_from_template(protocol.model_ready_template,
                                                      to=f'decision_agent@{config.domain}',
                                                      body=model_info)
        return model_ready_msg

    class PrepareModelBehaviour(OneShotBehaviour):
        async def run(self):
            message = message_from_template(request_model_from_db_template,
                                            body=self.agent.currency_symbol,
                                            to='data_agent@127.0.0.1')
            await self.send(message)
            reply = await self.receive(10)
            model = jsonpickle.loads(reply.body)
            if not model:
                self.agent.log.debug("No model found in db")
                self.agent.add_behaviour(self.agent.training_behaviour)
            else:
                self.agent.log.debug("Retrieved model from db")
                self.agent.model = model
                self.agent.has_strategy = True
                msg = self.agent.prepare_model_ready_message()
                await self.send(msg)

            self.agent.startup_done = True

    class TrainingRequestBehaviour(CyclicBehaviour):
        async def run(self):
            request = await self.receive(config.timeout)
            if request:
                if self.agent.startup_done and self.agent.has_strategy:
                    msg = self.agent.prepare_model_ready_message()
                    await self.send(msg)
                else:
                    pass  # odpowiedź nastąpi po treningu lub załadowaniu modelu z bazy

    class TrainBehaviour(OneShotBehaviour):
        def __init__(self, *args, **kwargs):
            super(StrategyAgent.TrainBehaviour, self).__init__()
            self.workers = []
            self.job_manager = None

        async def on_start(self):
            self.workers = [f'strategy_agent_worker_{self.agent.currency_symbol}_1@{domain}' for _ in range(2)]
            self.job_manager = JobManager(workers=self.workers)
            for worker_jid in self.workers:
                await StrategyAgentWorker(worker_jid, worker_jid, self.agent.currency_symbol).start(auto_register=True)

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
                population = [genotype for (genotype, cost) in
                              sorted(zip(population, costs), key=lambda x: x[1], reverse=True)]
                population = population[:population_size]

            best = population[0]
            model = Model(currency=self.agent.currency_symbol, short_mean=best[0], long_mean=best[1])
            self.agent.model = model

            message = message_from_template(save_model_to_db_template,
                                            to="data_agent@127.0.0.1",
                                            body=jsonpickle.dumps(model))
            await self.send(message)

            self.agent.has_strategy = True
            self.agent.log.debug('Training done!')

            msg = self.agent.prepare_model_ready_message()
            await self.send(msg)

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
                    reply = await self.receive(timeout=config.timeout)
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
                    if decision(self.agent.model.short_mean, self.agent.model.long_mean, self.agent.decision_records):
                        reply = message_from_template(give_positive_decision_template, to=str(msg.sender))
                        self.agent.log.debug('I sent give_positive_decision_template message!')
                    else:
                        reply = message_from_template(give_negative_decision_template, to=str(msg.sender))
                        self.agent.log.debug('I sent give_negative_decision_template message!')
                    await self.send(reply)
                else:
                    # trwa trening, nie można dać decyzji
                    reply = message_from_template(give_decision_not_available_template, to=str(msg.sender))
                    await self.send(reply)
                    self.agent.log.debug('I sent give_decision_not_available_template message!')

    class PrepareDataBehaviour(OneShotBehaviour):
        async def run(self):
            msg = tools.create_message(to="data_agent@127.0.0.1",
                                       performative="inform", ontology="history",
                                       body=jsonpickle.encode(
                                           value=(self.agent.currency_symbol, 300)))  # jeśli dane z ostatnich dni

            await self.send(msg)
            reply = await self.receive(10)
            records = jsonpickle.loads(reply.body)
            # print(records)
            self.agent.decision_records = list(map(lambda x: x.close, records))
            self.agent.add_behaviour(StrategyAgent.GiveDecisionBehaviour(), request_decision_template)
            # print(self.agent.decision_records)


if __name__ == '__main__':
    data_agent = DataAgent("data_agent@127.0.0.1", "data_agent")
    data_agent.start(auto_register=False)
    agent = StrategyAgent(f'strategy_agent_worker@{domain}', 'strategy_agent_worker1', "USDT")
    agent.start(auto_register=True)
