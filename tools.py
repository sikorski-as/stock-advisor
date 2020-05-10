import json
import logging
import sys

from spade.message import Message
from spade.template import Template


def to_json(data: dict) -> str:
    return json.dumps(data)


def from_json(data: str) -> dict:
    return json.loads(data)


def make_logger(name: str, level=None, filename: str = None, format: str = None) -> logging.Logger:
    """
    Creates logger in a simple manner.

    :param name: name for the logger
    :param level: visibility level of the logger (default: logging.DEBUG)
    :param filename: output filename (default: stdout)
    :param format: format of the output (default: [%(levelname)s][%(name)s][%(asctime)s]: %(message)s)
    """
    if not isinstance(name, str):
        name = str(name)

    format = format if format is not None \
        else '[%(levelname)s][%(name)s][%(asctime)s]: %(message)s'
    formatter = logging.Formatter(format)

    if filename is not None:
        handler = logging.FileHandler(filename)
    else:
        handler = logging.StreamHandler(sys.stdout)

    handler.setFormatter(formatter)

    log = logging.getLogger(name)
    log.addHandler(handler)

    if level is not None:
        log.setLevel(level)
    else:
        log.setLevel(logging.DEBUG)

    return log


def create_template(performative: str, ontology: str) -> Template:
    template = Template()
    template.set_metadata("performative", performative)
    template.set_metadata("ontology", ontology)
    return template


def create_message(to: str, performative: str, ontology: str, body: str) -> Message:
    message = Message(to=to)
    message.set_metadata("performative", performative)
    message.set_metadata("ontology", ontology)
    message.body = body
    return message
