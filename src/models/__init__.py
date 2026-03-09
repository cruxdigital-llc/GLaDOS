"""GLaDOS structured domain models for spec artifacts."""

from .requirements import Requirements, SuccessCriterion
from .plan import Plan, PlanPhase
from .spec import Spec, DataModel, APIEndpoint, EdgeCase
from .tasks import TaskBreakdown, Task, TaskStatus

__all__ = [
    "Requirements",
    "SuccessCriterion",
    "Plan",
    "PlanPhase",
    "Spec",
    "DataModel",
    "APIEndpoint",
    "EdgeCase",
    "TaskBreakdown",
    "Task",
    "TaskStatus",
]
