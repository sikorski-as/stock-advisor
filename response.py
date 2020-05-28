import datetime
import enum

import tools


class NoValue(enum.Enum):
    def __repr__(self):
        return '<%s>' % self.name


class Status(NoValue):
    ACTIVE = "Active"
    DONE = "Done"
    FAIL = "Fail"


class Type(NoValue):
    TRAIN = 'Train'
    DECISION = 'Decision'
    LIST = 'List'


class Response:

    def __init__(self):
        self._type = None
        self._status: Status = Status.ACTIVE
        self._body = None
        self._date = datetime.datetime.now()

    @classmethod
    def basic_response(cls):
        resp = Response()
        resp.status = Status.ACTIVE
        resp.body = 'Request received.'
        return resp

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, status):
        self._status = status
        self._date = datetime.datetime.now()

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, type):
        self._type = type
        self._date = datetime.datetime.now()

    @property
    def date(self):
        return self._date

    @property
    def body(self):
        return self._body

    @body.setter
    def body(self, body):
        self._body = body
        self._date = datetime.datetime.now()

    def get_json(self):
        """
        :return: json version of response
        """
        response = {"status": self.status.value, "body": self.body, "date": self._date, "type": self._type.value}
        return tools.to_json(response)

    def __repr__(self):
        return f"{self.status.value, self.body, self._date}"
