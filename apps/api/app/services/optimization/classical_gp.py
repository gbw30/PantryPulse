"""Conventional equal-weight objective on the shared physical region."""

from app.services.optimization.objective import attach


def attach_classical(model, policy=None):
    return attach(model, research=False)
