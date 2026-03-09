"""Domain models for the implement-feature task breakdown artifact."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

try:
    import dspy
except ImportError:
    dspy = None


class TaskStatus(str, Enum):
    """Status of an implementation task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class Task(BaseModel):
    """A single implementation task."""

    id: str = Field(description="Short unique identifier (e.g. 'T1', 'T2')")
    title: str = Field(description="Brief title of the task")
    description: str = Field(description="What needs to be done")
    status: TaskStatus = Field(default=TaskStatus.PENDING, description="Current status of the task")
    files_to_modify: list[str] = Field(
        default_factory=list,
        description="File paths that will be created or modified",
    )
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="Conditions that must be met for this task to be considered done",
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="IDs of tasks that must complete before this one",
    )


class TaskBreakdown(BaseModel):
    """Structured task breakdown for implementation, replacing freeform tasks.md."""

    tasks: list[Task] = Field(description="Ordered list of implementation tasks")

    def pending_tasks(self) -> list[Task]:
        """Return tasks that are not yet done."""
        return [t for t in self.tasks if t.status != TaskStatus.DONE]

    def next_task(self) -> Task | None:
        """Return the next actionable task (pending with all dependencies met)."""
        done_ids = {t.id for t in self.tasks if t.status == TaskStatus.DONE}
        for task in self.tasks:
            if task.status == TaskStatus.PENDING and all(d in done_ids for d in task.depends_on):
                return task
        return None


# ---------------------------------------------------------------------------
# DSPy Signature
# ---------------------------------------------------------------------------

if dspy is not None:

    class GenerateTaskBreakdown(dspy.Signature):
        """Break a specification into actionable implementation tasks."""

        spec_json: str = dspy.InputField(desc="JSON-serialized Spec model")
        project_context: str = dspy.InputField(desc="Relevant project context (file structure, patterns)")
        task_breakdown: TaskBreakdown = dspy.OutputField(desc="Structured task breakdown")
