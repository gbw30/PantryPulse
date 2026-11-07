"""Shared v1 stub error: a frozen route whose lane task has not landed answers 501 naming it."""


class NotImplementedV1(NotImplementedError):
    code = "NOT_IMPLEMENTED"

    def __init__(self, task: str):
        super().__init__(task)
        self.details = {"task": task}
