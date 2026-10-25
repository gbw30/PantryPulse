"""Bounded local adaptation, not a reproduction of the paper's endogenous model."""

from app.services.optimization.objective import attach


def attach_research(model, policy=None):
    return attach(model, research=True)
