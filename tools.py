import json
import logging
import sys
import uuid
from itertools import tee
from typing import List, Dict, Tuple

from spade.message import Message
from spade.template import Template


def to_json(data) -> str:
    return json.dumps(data, indent=4, sort_keys=True, default=str)


def from_json(data: str):
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


def make_template(**kwargs) -> Template:
    """
    Makes template with given metadata.

    :param kwargs: keyword='value' pairs for template's metadata dict

    Example:
        ``decision_request_template = make_template(performative='request', what='decision', currency='BTC')``
    """
    return Template(metadata=kwargs)


def message_from_template(template: Template, **kwargs) -> Message:
    """
    Makes a messsage from a template.

    :param template: template to create message from
    :param kwargs: fields of the message to overwrite the template ones
    :return: message created from template

    Example:
        ``msg = message_from_template(decision_request_template, to='decision_agent@domain')``
    """

    def from_template_or_kwargs(attrname):
        try:
            return kwargs[attrname]
        except KeyError:
            return getattr(template, attrname, None)

    return Message(
        sender=from_template_or_kwargs('sender'),
        to=from_template_or_kwargs('to'),
        body=from_template_or_kwargs('body'),
        thread=from_template_or_kwargs('thread'),
        metadata=from_template_or_kwargs('metadata')
    )


def reply_from_template(msg: Message, template: Template) -> Message:
    """
    Creates a message from a template and switches sender and receipent of the original message.

    :param msg: message to make reply for
    :param template: template of the messsage
    :return: message created from template with switched sender and receipent
    """
    return message_from_template(template, sender=str(msg.to), to=str(msg.sender), thread=msg.thread)


def make_uuid() -> str:
    """
    Generates an unique ID (for a conversation ID for example).
    """
    return str(uuid.uuid1())


def split_into_chunks(alist: List, nchunks: int) -> List[List]:
    """
    Splits list into equal or almost equal parts.
    If sequence cannot be divided into equal parts, the last parts will be shorter

    :param alist: list to split
    :param nchunks: number of chunks to split list to
    :param as_ranges: True if ranges of a list should be returned instead of list
    :return: list of chunks
    """

    def chunks(alist, nchunks):
        d, r = divmod(len(alist), nchunks)
        for i in range(nchunks):
            si = (d + 1) * (i if i < r else r) + d * (0 if i < r else i - r)
            ei = si + (d + 1 if i < r else d)
            yield alist[si:ei]

    return list(chunks(alist, nchunks))
