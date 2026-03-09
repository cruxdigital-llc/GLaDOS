"""Domain models for the plan-feature requirements artifact."""

from __future__ import annotations

from pydantic import BaseModel, Field

try:
    import dspy
except ImportError:
    dspy = None


class SuccessCriterion(BaseModel):
    """A single measurable success criterion for a feature."""

    description: str = Field(description="What must be true for the feature to be considered successful")
    verification_method: str = Field(description="How this criterion will be verified (e.g. test, manual check)")


class Requirements(BaseModel):
    """Structured requirements for a feature, replacing freeform requirements.md."""

    feature_name: str = Field(description="Kebab-case name of the feature (e.g. 'user-authentication')")
    goal: str = Field(description="High-level goal of this feature — what problem does it solve?")
    success_criteria: list[SuccessCriterion] = Field(
        description="Measurable criteria that define when the feature is complete"
    )
    constraints: list[str] = Field(
        default_factory=list,
        description="Technical or business constraints (e.g. 'Must use Auth0', 'No new dependencies')",
    )
    personas: list[str] = Field(
        default_factory=list,
        description="Active persona names for this feature (e.g. ['architect', 'qa'])",
    )


# ---------------------------------------------------------------------------
# DSPy Signature (available when dspy-ai is installed)
# ---------------------------------------------------------------------------

if dspy is not None:

    class GenerateRequirements(dspy.Signature):
        """Analyze a feature request and produce structured requirements."""

        feature_description: str = dspy.InputField(desc="User's description of the desired feature")
        project_context: str = dspy.InputField(desc="Relevant project context (mission, roadmap, status)")
        requirements: Requirements = dspy.OutputField(desc="Structured requirements for the feature")
