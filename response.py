import enum

import tools


class NoValue(enum.Enum):
    def __repr__(self):
        return '<%s.%s>' % (self.__class__.__name__, self.name)


class Status(NoValue):
    ACTIVE = "Active"
    DONE = "Done"
    FAIL = "Fail"


class Response:

    def __init__(self):
        self.status: Status = Status.ACTIVE
        self.body = None

    def get(self):
        response = {"status": self.status.value, "body": self.body}
        return tools.to_json(response)

    def __repr__(self):
        return f"{self.status.value, self.body}"
