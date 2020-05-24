import asyncio

import jsonpickle
from spade import agent
from spade.behaviour import CyclicBehaviour, OneShotBehaviour

import protocol
import tools
from strategy_agent import StrategyAgent
import config


class DecisionAgent(agent.Agent):
    def __init__(self, jid, password, verify_security=False):
        super().__init__(jid, password, verify_security)
        self.log = tools.make_logger(self.jid)
        self.strategy_agents = set()
        self.requested_training_of = {}

    async def setup(self):
        self.log.info('Starting!')

        self.add_behaviour(self.TrainBehaviour(), protocol.request_train_template)
        self.add_behaviour(self.TrainResponseBehaviour(), protocol.model_ready_template)

        list_request_template = tools.create_template("request", "list")
        self.add_behaviour(self.ListBehaviour(), list_request_template)

        list_response_template = tools.create_template("inform", "list")
        self.add_behaviour(self.ListResponseBehaviour(), list_response_template)

        decision_request_template = tools.create_template("request", "decision")
        self.add_behaviour(self.DecisionBehaviour(), decision_request_template)
        self.add_behaviour(self.DecisionResponseBehaviour(), protocol.give_decision_template)

    async def ensure_strategy_agent(self, currency_symbol):
        jid = f'{currency_symbol}@{config.domain}'

        if jid not in self.strategy_agents:
            strategy_agent = StrategyAgent(jid, currency_symbol, currency_symbol)
            await strategy_agent.start(auto_register=True)
            self.strategy_agents.add(jid)

        return jid

    class TrainBehaviour(CyclicBehaviour):
        async def run(self):
            message = await self.receive(config.timeout)
            if message is not None:
                self.agent.log.info(f'Received request of training {message.body}')
                jid = await self.agent.ensure_strategy_agent(message.body.lower())
                request = tools.message_from_template(protocol.request_train_template,
                                                      to=jid,
                                                      body=message.body)
                self.agent.requested_training_of[message.body] = True
                await self.send(request)

    class TrainResponseBehaviour(CyclicBehaviour):
        async def run(self):
            response = await self.receive(config.timeout)
            if response:
                currency, *_ = jsonpickle.decode(response.body)
                if self.agent.requested_training_of.get(currency, False):
                    self.agent.requested_training_of[currency] = False
                    response_to_interface = tools.message_from_template(protocol.model_ready_template,
                                                                        to=f'interface_agent@{config.domain}',
                                                                        body=response.body)
                    await self.send(response_to_interface)

    class ListBehaviour(CyclicBehaviour):
        async def run(self):
            models_request = await self.receive(config.timeout)
            if models_request:
                da_request = tools.create_message(f"data_agent@{config.domain}", "request", "list", "")
                self.agent.log.debug(f'{models_request.sender} is asking for list of models, asking {da_request.to}')
                await self.send(da_request)

    class ListResponseBehaviour(CyclicBehaviour):
        async def run(self):
            da_response = await self.receive(config.timeout)
            if da_response is not None:
                models = da_response.body
                try:
                    parsed_models = jsonpickle.decode(da_response.body)
                    assert type(parsed_models) == list

                    nmodels = len(parsed_models)
                    if nmodels == 0:
                        models = jsonpickle.encode(None)

                    self.agent.log.debug(
                        f'{da_response.sender} responded, {nmodels} models available. Informing interface.')
                    models_list = tools.create_message(f"interface_agent@{config.domain}", "inform", "list", models)
                    await self.send(models_list)
                except:
                    self.agent.log.error(
                        f'List of models from {da_response.sender} is invalid. No models available.')
                    models = jsonpickle.encode(None)
                    models_list = tools.create_message(f"interface_agent@{config.domain}", "inform", "list", models)
                    await self.send(models_list)

    class DecisionBehaviour(CyclicBehaviour):
        async def run(self):
            message = await self.receive(config.timeout)
            if message is not None:
                currency = message.body.lower()
                request = tools.message_from_template(protocol.request_decision_template,
                                                      to=f'{currency}@{config.domain}')
                self.agent.log.info(f'{message.sender} is asking for decision, asking {request.to} for an answer')
                await self.agent.ensure_strategy_agent(currency)
                await asyncio.sleep(3)
                await self.send(request)

    class DecisionResponseBehaviour(CyclicBehaviour):
        async def run(self):
            message = await self.receive(config.timeout)
            if message is not None:
                answer = message.metadata['answer']
                self.agent.log.info(f'{message.sender} says "{answer}"')
                currency = str(message.sender).split('@')[0]  # to bardzo brzydki trick
                body = jsonpickle.encode([currency, message.metadata['answer']])
                response_to_interface = tools.create_message(to=f'interface_agent@{config.domain}',
                                                             performative='inform',
                                                             ontology='decision', body=body)
                await self.send(response_to_interface)
                self.agent.log.info('Decision sent to interface!')


if __name__ == '__main__':
    agent = DecisionAgent('decision_agent@localhost', 'decision_agent')
    agent.start()
