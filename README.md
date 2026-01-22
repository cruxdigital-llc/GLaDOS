# GLaDOS

**GLaDOS** (Generative Logic and Documentation Operating System) is an advanced agentic framework designed to structure, trace, and enhance the software development lifecycle when using LLMs.

It transforms vague instructions into a rigorous, verifiable process by enforcing **Traceability**, **Role-Based Review**, and **Modular Workflows**.

---

## Features

### 🔍 Strict Observability (`specs/`)
Every unit of work (Feature, Bugfix, Plan) creates a dedicated directory in `specs/[YYYY-MM-DD]_[Name]/`. It acts as a "Flight Recorder," logging every decision, prompt, and file change. The high-level state is maintained in `PROJECT_STATUS.md`, while long-term artifacts (`MISSION.md`, `ROADMAP.md`) live in the root.

### 🎭 Dynamic Personas
GLaDOS forces the agent to adopt specific viewpoints during planning and verification.
-   **Product Manager**: "Is this valuable?"
-   **Architect**: "Is this scalable?"
-   **QA**: "Is this breakable?"
*Add your own personas (e.g., Security Expert) by dropping files into `src/personas`.*

### ⚡ Split Lifecycles
Development is broken into discrete, verifying steps:
**Plan** → **Spec** → **Implement** → **Verify**.
This prevents "hallucination spirals" by validating state at each checkpoint.

### 🧩 Modular Architecture
Logic is shared across workflows using Modules (`src/modules/`).
-   **Observability**: Standardized logging.
-   **Capabilities**: Introspects available tools (Browser, DB, MCPs) to enhance execution.
-   **Persona Review**: Iterates through active stakeholders.

---

## Installation

GLaDOS is installed via a shell script that injects the workflows into your project.

### Claude Code Mode
Installs into `.claude/commands` as standard markdown files, enabling usage with Claude Code slash commands.

```bash
./bin/glados-install.sh --mode claude
```

### Antigravity Mode
Installs into `.agent/workflows` with YAML frontmatter for IDE integration.

```bash
./bin/glados-install.sh --mode antigravity
```

### Gemini CLI Mode
Installs as an Agent Skill into `.gemini/skills/glados` (following the Agent Skills standard).

```bash
./bin/glados-install.sh --mode gemini
```

### Direct Mode
Installs into `glados/` in your project root. Useful for manual inspection or custom setups.

```bash
./bin/glados-install.sh --mode direct
```

---

## Quick Start Guide

Choose the path that matches your project state.

### Path A: Information Greenfield (New Project)
*Best for starting from scratch.*

1.  **Define the Mission**:
    Run `/mission` to create `MISSION.md`. Establishing the "Why" and "Who" ensures all future agents align with your goals.
2.  **Plan the Product**:
    Run `/plan-product` to create `ROADMAP.md` and `TECH_STACK.md`.
3.  **Start Building**:
    Run `/plan-feature` to pick an item from your roadmap and begin the development loop.

### Path B: Brownfield (Existing Codebase)
*Best for integrating GLaDOS into an active repo.*

1.  **Map the Territory**:
    Run `/review-codebase`. GLaDOS will analyze your file structure, infer your tech stack, and populate `PROJECT_STATUS.md`.
2.  **Codify Knowledge**:
    Run `/establish-standards`. This interactively extracts "tribal knowledge" (e.g., "How do we handle errors?") into `standards/` files so future agents follow your rules.
3.  **Align on Goals**:
    Run `/mission` to ensure the agent understands the project's high-level purpose.
4.  **Resume Work**:
    Run `/identify-bug` or `/plan-feature` to start contributing.

---

## Core Workflows

Once installed, use these workflows to drive development.

### 1. Strategy & Setup
| Command | Description |
| :--- | :--- |
| `/mission` | Creates/Updates `MISSION.md` (North Star). |
| `/plan-product` | Generates `ROADMAP.md` & `TECH_STACK.md`. |
| `/establish-standards` | Interactive interview to create `standards/*.md`. |
| `/review-codebase` | Spider the directory to build `PROJECT_STATUS.md`. |

### 2. The Development Loop
For every feature, follow this 4-step cycle:

1.  **`/plan-feature`**: Analyzes requirements, consults the Roadmap, drafts a high-level approach.
2.  **`/spec-feature`**: Refines the plan into a detailed `spec.md`. Triggers **Persona Review**.
3.  **`/implement-feature`**: Writes code based on the spec. Updates traces in `specs/`.
4.  **`/verify-feature`**: Runs tests, verifies against the spec, and updates the `walkthrough.md`.

### 3. Maintenance
| Command | Description |
| :--- | :--- |
| `/identify-bug` | creates a reproduction plan before touching code. |
| `/plan-fix` | Lightweight planning for smaller issues. |
| `/implement-fix` | Targeted code changes. |
| `/retrospect` | Review recent work to improve `standards/` or process. |

---

## Example Scenario: "Adding a Login Page"

Here is what a typical GLaDOS interaction looks like.

**1. User runs `/plan-feature`**
> User: "We need a login page for the admin panel."
> Agent: Creates `specs/2024-10-24_admin_login/`. Reads `MISSION.md`. Checks `ROADMAP.md`.
> **Output**: `specs/.../implementation_plan.md` outlining the Auth0 integration.

**2. User runs `/spec-feature`**
> Agent: Reads the plan. Simulates strict reviews.
> *Persona (Security)*: "Ensure we use Rotation Tokens."
> *Persona (Product)*: "Don't forget the 'Forgot Password' flow."
> **Output**: A comprehensive `spec.md` approved by simulated stakeholders.

**3. User runs `/implement-feature`**
> Agent: Writes code in `src/auth/`. Updates `specs/.../trace.md` with every file change.
> **Output**: The actual code changes.

**4. User runs `/verify-feature`**
> Agent: Runs `npm test`. Clicks through the browser (if available).
> **Output**: `walkthrough.md` with screenshots/logs proving it works.

---

## Customization (Overlays)

You can customize GLaDOS without forking it using **Overlays**.

1.  Create `src/overlays/my_overlay/`.
2.  Copy a file (e.g., `src/workflows/plan_feature.md`) to your overlay directory.
3.  Edit it.
4.  Install with the overlay:

```bash
./bin/glados-install.sh --mode antigravity --overlay my_overlay
```

---

## Contributing

1.  **Workflows** in `src/workflows/` define the high-level steps.
2.  **Modules** in `src/modules/` contain shared logic.
3.  **Personas** in `src/personas/` define agent roles.

Please ensure any new feature includes a corresponding Module or Persona if applicable to keep workflows DRY.
