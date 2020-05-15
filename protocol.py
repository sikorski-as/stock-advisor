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
give_positive_decision_template = give_decision_template | make_template(answer='yes')

"positive_decision from strategy agent"
give_negative_decision_template = give_decision_template | make_template(answer='no')

#
# Strategy Agent Worker (SAW)
#
request_cost_computation = make_template(performative='request', what='cost function')

please_retransfer = make_template(performative='please', what='retransfer cost function')
