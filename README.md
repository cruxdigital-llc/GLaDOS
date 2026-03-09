# GLaDOS

**GLaDOS** (Generative Logic and Documentation Operating System) is an advanced agentic framework designed to structure, trace, and enhance the software development lifecycle when using LLMs.

It transforms vague instructions into a rigorous, verifiable process by enforcing **Traceability**, **Role-Based Review**, and **Modular Workflows**.

---

## Features

### Strict Observability (`specs/`)
Every unit of work (Feature, Bugfix, Plan) creates a dedicated directory in `specs/[YYYY-MM-DD]_[Name]/`. It acts as a "Flight Recorder," logging every decision, prompt, and file change. The high-level state is maintained in `PROJECT_STATUS.md`, while long-term artifacts (`MISSION.md`, `ROADMAP.md`, `TECH_STACK.md`) live in `product-knowledge/`.

### Dynamic Personas
GLaDOS forces the agent to adopt specific viewpoints during planning and verification.
-   **Product Manager**: "Is this valuable?"
-   **Architect**: "Is this scalable?"
-   **QA**: "Is this breakable?"

Personas support three modes: **review** (critique during gates), **operating** (drive session behavior), and **hybrid** (both). Add your own by dropping files into `src/personas`.

### Split Lifecycles
Development is broken into discrete, verifying steps:
**Plan** → **Spec** → **Implement** → **Verify**.
This prevents "hallucination spirals" by validating state at each checkpoint.

### DSPy-Powered Structured Specs
Spec artifacts (`requirements`, `plan`, `spec`, `tasks`) are defined as **Pydantic domain models** in `src/models/` and generated via **DSPy pipeline modules** in `src/pipeline/`. Workflows call the `bin/glados-dspy` CLI to run DSPy's `ChainOfThought` against your configured LM, producing validated JSON artifacts stored in each `specs/` directory. All spec data is stored as DSPy-native JSON — module state (`.json`) plus extracted data (`_data.json`) — enabling future optimization via DSPy's `BootstrapFewShot`, `MIPROv2`, and other optimizers.

### Standards Gate
Documented standards are enforced automatically at pre- and post-implementation checkpoints using three severity tiers:
-   **must**: Blocks the workflow.
-   **should**: Warning in the trace.
-   **may**: Informational.

### Philosophies
Beyond standards (the *what*), GLaDOS tracks **philosophies** (the *why*) — high-level design principles like "All APIs should be RESTful" or "Zero-downtime deployments are non-negotiable." Core philosophies are enforced as blocking constraints.

### Silent Capture
The `pattern-observer` module passively logs implicit standards and philosophies as they emerge during normal work — user corrections, repeated patterns, and explicit statements get captured in `product-knowledge/observations/` for later review.

### Modular Architecture
Logic is shared across workflows using Modules (`src/modules/`).
-   **Observability**: Standardized logging.
-   **Persona Context**: Review and operating persona management.
-   **Standards Gate**: Automated enforcement at checkpoints.
-   **Pattern Observer**: Passive implicit-pattern detection.
-   **Capabilities**: Introspects available tools (Browser, DB, MCPs).

---


GLaDOS installs directly into your project, creating a `product-knowledge/` directory for configuration and product knowledge.

### Basic Installation

To install (or update) GLaDOS, run the install script and specify your environment:

**Claude Code:**
```bash
./bin/glados-install.sh --mode claude
```
*Installs commands to `.claude/commands/glados`.*

**Antigravity (IDE):**
```bash
./bin/glados-install.sh --mode antigravity
```
*Installs workflows to `.agent/workflows/glados`.*

**Gemini CLI:**
```bash
./bin/glados-install.sh --mode gemini
```
*Installs as a skill to `.gemini/skills/glados`.*

**Installing into a different project:**

By default, GLaDOS installs into the current directory. Use `--target` to install into another repo:

```bash
./bin/glados-install.sh --mode claude --target /path/to/your/project
```

### DSPy Engine Setup

The installer copies the DSPy engine (models, pipeline, CLI script) into your project. To use it, install the Python dependencies:

```bash
pip install dspy-ai pydantic
```

Then set the `GLADOS_LM` environment variable to tell DSPy which LM to use:

```bash
export GLADOS_LM="openai/gpt-4o"           # or anthropic/claude-sonnet-4-20250514, etc.
```

The matching API key must also be set (e.g. `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`).

### The `product-knowledge/` Directory

Every installation scaffolds a `product-knowledge/` directory in your project root:
-   `product-knowledge/PROJECT_STATUS.md`: The high-level state of your project.
-   `product-knowledge/MISSION.md`: The product mission and north star.
-   `product-knowledge/ROADMAP.md`: The strategic roadmap.
-   `product-knowledge/TECH_STACK.md`: Technology stack decisions.
-   `product-knowledge/bin/glados-dspy`: The DSPy CLI engine.
-   `product-knowledge/personas/`: Custom personas (add your own here!).
-   `product-knowledge/overlays/`: Directory for local overlays to customize workflows.
-   `product-knowledge/standards/`: Documented coding and architectural standards.
-   `product-knowledge/philosophies/`: High-level design principles and agreements.
-   `product-knowledge/observations/`: Staging area for implicitly detected patterns.

### Updates & Overlays

To update your commands or ingest new local overlays from `product-knowledge/overlays/`, run:

```bash
./bin/glados-update.sh --ingest-overlays
```


---

## Quick Start Guide

Choose the path that matches your project state.

### Path A: Information Greenfield (New Project)
*Best for starting from scratch.*

1.  **Define the Mission**:
    Run `/glados/mission` to create `product-knowledge/MISSION.md`. Establishing the "Why" and "Who" ensures all future agents align with your goals.
2.  **Plan the Product**:
    Run `/glados/plan-product` to create `product-knowledge/ROADMAP.md` and `product-knowledge/TECH_STACK.md`.
3.  **Start Building**:
    Run `/glados/plan-feature` to pick an item from your roadmap and begin the development loop.

### Path B: Brownfield (Existing Codebase)
*Best for integrating GLaDOS into an active repo.*

1.  **Full Onboarding** (recommended):
    Run `/glados/adopt-codebase`. This orchestrates the full brownfield sequence: structural analysis, standards extraction, philosophy discovery, and mission alignment.
2.  **Or, Step by Step**:
    1.  Run `/glados/review-codebase` to analyze your file structure and populate `PROJECT_STATUS.md`.
    2.  Run `/glados/establish-standards` to extract tribal knowledge into `standards/` files.
    3.  Run `/glados/mission` to ensure the agent understands the project's purpose.
3.  **Resume Work**:
    Run `/glados/identify-bug` or `/glados/plan-feature` to start contributing.

### Path C: Autonomous Mode
*Best for hands-off development.*

1.  **Ignite the Loop**:
    Run `autonomous-loop`.
2.  **Bootstrap**:
    -   **Empty Repo**: It will ask for your Vision and Success Criteria once, then take over.
    -   **Existing Repo**: It will read your `product-knowledge/ROADMAP.md` and start executing the next active task.
3.  **Sit Back**:
    The agent will Plan, Spec, Implement, and Verify features in a continuous loop, answering its own questions based on your defined Mission and Standards.

---

## Core Workflows

Once installed, use these workflows to drive development.

### 1. Strategy & Setup
| Command | Description |
| :--- | :--- |
| `/glados/mission` | Creates/Updates `product-knowledge/MISSION.md` (North Star). |
| `/glados/plan-product` | Generates `product-knowledge/ROADMAP.md` & `product-knowledge/TECH_STACK.md`. |
| `/glados/establish-standards` | Interactive interview to create `standards/*.md`. |
| `/glados/review-codebase` | Spider the directory to build `PROJECT_STATUS.md`. |
| `/glados/adopt-codebase` | Full brownfield onboarding sequence. |

### 2. The Development Loop
For every feature, follow this 4-step cycle:

1.  **`/glados/plan-feature`**: Gathers requirements, runs the DSPy engine to generate `requirements_data.json` and `plan_data.json`.
2.  **`/glados/spec-feature`**: Runs DSPy to generate `spec_data.json` from the plan. Triggers **Persona Review**.
3.  **`/glados/implement-feature`**: Runs DSPy to generate `tasks_data.json`, writes code based on the spec. Updates traces in `specs/`.
4.  **`/glados/verify-feature`**: Runs tests, verifies against `spec_data.json` and `tasks_data.json`, updates the `walkthrough.md`.

### 3. Maintenance
| Command | Description |
| :--- | :--- |
| `/glados/identify-bug` | Creates a reproduction plan before touching code. |
| `/glados/plan-fix` | Lightweight planning for smaller issues. |
| `/glados/implement-fix` | Targeted code changes. |
| `/glados/retrospect` | Review recent work to improve `standards/` or process. |
| `/glados/recombobulate` | Systematically clean up vibe debt, formalize patterns, audit standards. |
| `/glados/consolidate` | Alias for `/glados/recombobulate`. |

---

## DSPy CLI Reference

The `glados-dspy` script is the engine behind structured spec generation:

```bash
# Generate requirements and plan from a feature description
python3 product-knowledge/bin/glados-dspy plan \
  --feature "User authentication with Auth0" \
  --context-dir product-knowledge/ \
  --output-dir specs/2024-03-08_feature_user-auth/

# Generate spec from requirements + plan
python3 product-knowledge/bin/glados-dspy spec \
  --input-dir specs/2024-03-08_feature_user-auth/ \
  --context-dir product-knowledge/ \
  --output-dir specs/2024-03-08_feature_user-auth/

# Generate task breakdown from spec
python3 product-knowledge/bin/glados-dspy tasks \
  --input-dir specs/2024-03-08_feature_user-auth/ \
  --context-dir product-knowledge/ \
  --output-dir specs/2024-03-08_feature_user-auth/

# View a saved artifact
python3 product-knowledge/bin/glados-dspy show \
  --input-dir specs/2024-03-08_feature_user-auth/ \
  --artifact spec
```

**Options:**
- `--lm <provider/model>`: Override `GLADOS_LM` env var (e.g. `openai/gpt-4o`)
- `--format json|text`: Output format (default: `json`)

---

## Example Scenario: "Adding a Login Page"

Here is what a typical GLaDOS interaction looks like.

**1. User runs `/glados/plan-feature`**
> User: "We need a login page for the admin panel."
> Agent: Creates `specs/2024-10-24_feature_admin-login/`. Runs `glados-dspy plan` with project context.
> **Output**: `requirements_data.json` and `plan_data.json` — structured, validated specs stored as DSPy artifacts.

**2. User runs `/glados/spec-feature`**
> Agent: Runs `glados-dspy spec` which reads the plan and generates a detailed spec. Simulates strict reviews.
> *Persona (Security)*: "Ensure we use Rotation Tokens."
> *Persona (Product)*: "Don't forget the 'Forgot Password' flow."
> **Output**: `spec_data.json` — validated specification approved by simulated stakeholders.

**3. User runs `/glados/implement-feature`**
> Agent: Runs `glados-dspy tasks` to generate a task breakdown. Writes code in `src/auth/`. Updates `specs/.../README.md` trace with every file change.
> **Output**: The actual code changes, with each task marked `done` in `tasks_data.json`.

**4. User runs `/glados/verify-feature`**
> Agent: Reads `spec_data.json` and `tasks_data.json`. Runs `npm test`. Clicks through the browser (if available).
> **Output**: `walkthrough.md` with screenshots/logs proving it works.

---

## Customization (Overlays)

You can customize GLaDOS without forking it using **Overlays**.

1.  Create `src/overlays/my-overlay/`.
2.  Copy a file (e.g., `src/workflows/plan-feature.md`) to your overlay directory.
3.  Edit it.
4.  Install with the overlay:

```bash
./bin/glados-install.sh --mode antigravity --overlay my-overlay
```

---

## Playbook: Adopting GLaDOS in Your Team

See **[PLAYBOOK.md](PLAYBOOK.md)** for comprehensive guidance on:

-   **Solo quickstart**: Day-1 install through week-2 steady state.
-   **Recommended cadence**: Per-feature, weekly, monthly, and quarterly rituals.
-   **Team adoption**: A 4-stage evangelization path from Champion → Pair → Team → Multi-Team.
-   **Customization**: Adding personas, philosophies, and overlays.
-   **Anti-patterns**: Common mistakes that undermine adoption.
-   **Measuring success**: Signals that GLaDOS is delivering value.

---

## Contributing

1.  **Workflows** in `src/workflows/` define the high-level steps.
2.  **Modules** in `src/modules/` contain shared logic.
3.  **Models** in `src/models/` define structured Pydantic domain models for spec artifacts.
4.  **Pipeline** in `src/pipeline/` contains DSPy modules that compose models into generation pipelines.
5.  **Personas** in `src/personas/` define agent roles.

Please ensure any new feature includes a corresponding Module or Persona if applicable to keep workflows DRY.
