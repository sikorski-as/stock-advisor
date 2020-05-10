import json
import logging
import sys


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
