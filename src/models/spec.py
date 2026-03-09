"""Domain models for the spec-feature specification artifact."""

from __future__ import annotations

from pydantic import BaseModel, Field

try:
    import dspy
except ImportError:
    dspy = None


class DataModel(BaseModel):
    """A data model or schema change required by the feature."""

    name: str = Field(description="Name of the model/table (e.g. 'User', 'sessions')")
    fields: dict[str, str] = Field(
        description="Mapping of field name to type/description (e.g. {'email': 'str, unique'})"
    )
    relationships: list[str] = Field(
        default_factory=list,
        description="Relationships to other models (e.g. 'User has_many Sessions')",
    )


class APIEndpoint(BaseModel):
    """An API endpoint defined by the specification."""

    method: str = Field(description="HTTP method (GET, POST, PUT, DELETE, etc.)")
    path: str = Field(description="URL path (e.g. '/api/auth/login')")
    description: str = Field(description="What this endpoint does")
    request_body: dict[str, str] | None = Field(
        default=None,
        description="Expected request body fields and types",
    )
    response_body: dict[str, str] | None = Field(
        default=None,
        description="Expected response body fields and types",
    )


class EdgeCase(BaseModel):
    """An edge case or error scenario to handle."""

    scenario: str = Field(description="Description of the edge case")
    handling: str = Field(description="How this edge case should be handled")


class Spec(BaseModel):
    """Structured technical specification for a feature, replacing freeform spec.md."""

    data_models: list[DataModel] = Field(
        default_factory=list,
        description="Database schema or data model changes",
    )
    api_endpoints: list[APIEndpoint] = Field(
        default_factory=list,
        description="API endpoints to create or modify",
    )
    edge_cases: list[EdgeCase] = Field(
        default_factory=list,
        description="Edge cases and error handling scenarios",
    )
    security_considerations: list[str] = Field(
        default_factory=list,
        description="Security concerns and mitigations",
    )
    performance_considerations: list[str] = Field(
        default_factory=list,
        description="Performance concerns and strategies",
    )


# ---------------------------------------------------------------------------
# DSPy Signature
# ---------------------------------------------------------------------------

if dspy is not None:

    class GenerateSpec(dspy.Signature):
        """Generate a detailed technical specification from requirements and plan."""

        requirements_json: str = dspy.InputField(desc="JSON-serialized Requirements model")
        plan_json: str = dspy.InputField(desc="JSON-serialized Plan model")
        project_context: str = dspy.InputField(desc="Relevant project context (existing code, standards)")
        spec: Spec = dspy.OutputField(desc="Structured technical specification")
