"""Domain models for the plan-feature plan artifact."""

from __future__ import annotations

from pydantic import BaseModel, Field

try:
    import dspy
except ImportError:
    dspy = None


class PlanPhase(BaseModel):
    """A single phase in the implementation plan."""

    name: str = Field(description="Short name for this phase (e.g. 'Database Schema')")
    description: str = Field(description="What this phase accomplishes")
    dependencies: list[str] = Field(
        default_factory=list,
        description="Names of phases that must complete before this one",
    )
    complexity: str = Field(
        default="medium",
        description="Estimated complexity: low, medium, or high",
    )


class Plan(BaseModel):
    """Structured implementation plan for a feature, replacing freeform plan.md."""

    approach: str = Field(description="High-level summary of the implementation approach")
    phases: list[PlanPhase] = Field(description="Ordered phases of implementation")
    risks: list[str] = Field(
        default_factory=list,
        description="Identified risks and mitigation strategies",
    )
    open_questions: list[str] = Field(
        default_factory=list,
        description="Questions that need answers before or during implementation",
    )


# ---------------------------------------------------------------------------
# DSPy Signature
# ---------------------------------------------------------------------------

if dspy is not None:

    class GeneratePlan(dspy.Signature):
        """Generate a structured implementation plan from requirements."""

        requirements_json: str = dspy.InputField(desc="JSON-serialized Requirements model")
        project_context: str = dspy.InputField(desc="Relevant project context (tech stack, standards)")
        plan: Plan = dspy.OutputField(desc="Structured implementation plan")
