"""Registered-but-unbuilt v1 job handlers (W0-08b).

Admission answers 501 naming the owning task, and no supervisor advertises the contract, so a
stub job is never claimed. The owning lane replaces the handler and publisher.
"""

from app.services.v1_errors import NotImplementedV1


class NotBuiltHandler:
    def __init__(self, task: str):
        self.task = task

    def validate_input(self, payload):
        raise NotImplementedV1(self.task)

    def steps(self, validated, profile):
        raise NotImplementedV1(self.task)

    def execute_step(self, step, validated, prior, context):
        raise NotImplementedV1(self.task)

    @staticmethod
    def execution_capability():
        return None  # never advertised for execution


class NotBuiltPublisher:
    def __init__(self, task: str):
        self.task = task

    def validate(self, validated, outcomes):
        raise NotImplementedV1(self.task)

    def publish(self, connection, identity, package):
        raise NotImplementedV1(self.task)
