from spade.template import Template
from tools import make_template

"example template documentation string"
example_template = Template()

#
# General
#
ping_template = make_template(performative='ping')

#
# Data Agent (DA)
#
...

#
# Interface Agent (IA)
#
...

#
# Decision Agent (DecA)
#
...

#
# Strategy Agent (SA)
#
"request decision from strategy agent"
request_decision_template = make_template(performative='request', what='decision')

"give decision from strategy agent"
give_decision_template = make_template(performative='reply', what='decision')

"positive_decision from strategy agent"
give_positive_decision_template = make_template(performative='reply', what='decision', answer='yes')

"negative_decision from strategy agent"
give_negative_decision_template = make_template(performative='reply', what='decision', answer='no')

"decision not available"
give_decision_not_available_template = make_template(performative='reply', what='decision', answer='not available')

"request model from data agent"
request_model_from_db_template = make_template(performative='request', what='model')

"give model"
give_model_template = make_template(performative='reply', what='model')

"save model"
save_model_to_db_template = make_template(performative='request', what='save_model')

"give latest data"
give_data_template = make_template(performative='reply', what='data')
#
# Strategy Agent Worker (SAW)
#
request_cost_computation = make_template(performative='request', what='cost function')

please_retransfer = make_template(performative='please', what='retransfer cost function')

reply_historical_data = make_template(performative='reply', what='historical data')
