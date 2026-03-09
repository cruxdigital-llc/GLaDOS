"""DSPy pipeline modules for the GLaDOS feature development lifecycle.

These modules compose the Signatures from src/models/ into a multi-step
pipeline.  They use ChainOfThought for richer reasoning traces.

Requires ``dspy-ai``::

    pip install dspy-ai pydantic
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import dspy

# Support both in-repo and installed import paths.
_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_SRC = _SCRIPT_DIR.parent  # src/

if (_REPO_SRC / "models").is_dir():
    _models = importlib.import_module("src.models")
    _req_mod = importlib.import_module("src.models.requirements")
    _plan_mod = importlib.import_module("src.models.plan")
    _spec_mod = importlib.import_module("src.models.spec")
    _tasks_mod = importlib.import_module("src.models.tasks")
else:
    _models = importlib.import_module("glados_models")
    _req_mod = importlib.import_module("glados_models.requirements")
    _plan_mod = importlib.import_module("glados_models.plan")
    _spec_mod = importlib.import_module("glados_models.spec")
    _tasks_mod = importlib.import_module("glados_models.tasks")

GenerateRequirements = _req_mod.GenerateRequirements
GeneratePlan = _plan_mod.GeneratePlan
GenerateSpec = _spec_mod.GenerateSpec
GenerateTaskBreakdown = _tasks_mod.GenerateTaskBreakdown


class PlanFeature(dspy.Module):
    """Plan step: feature description -> Requirements + Plan."""

    def __init__(self) -> None:
        super().__init__()
        self.gen_requirements = dspy.ChainOfThought(GenerateRequirements)
        self.gen_plan = dspy.ChainOfThought(GeneratePlan)

    def forward(self, feature_description: str, project_context: str):
        req_result = self.gen_requirements(
            feature_description=feature_description,
            project_context=project_context,
        )
        plan_result = self.gen_plan(
            requirements_json=req_result.requirements.model_dump_json(),
            project_context=project_context,
        )
        return dspy.Prediction(
            requirements=req_result.requirements,
            plan=plan_result.plan,
        )


class SpecFeature(dspy.Module):
    """Spec step: Requirements + Plan -> Spec."""

    def __init__(self) -> None:
        super().__init__()
        self.gen_spec = dspy.ChainOfThought(GenerateSpec)

    def forward(self, requirements_json: str, plan_json: str, project_context: str):
        result = self.gen_spec(
            requirements_json=requirements_json,
            plan_json=plan_json,
            project_context=project_context,
        )
        return dspy.Prediction(spec=result.spec)


class ImplementFeature(dspy.Module):
    """Implement step: Spec -> TaskBreakdown."""

    def __init__(self) -> None:
        super().__init__()
        self.gen_tasks = dspy.ChainOfThought(GenerateTaskBreakdown)

    def forward(self, spec_json: str, project_context: str):
        result = self.gen_tasks(
            spec_json=spec_json,
            project_context=project_context,
        )
        return dspy.Prediction(task_breakdown=result.task_breakdown)
