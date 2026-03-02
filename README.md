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

Personas support three modes: **review** (critique during gates), **operating** (drive session behavior), and **hybrid** (both). Add your own by dropping files into `src/personas`.

### ⚡ Split Lifecycles
Development is broken into discrete, verifying steps:
**Plan** → **Spec** → **Implement** → **Verify**.
This prevents "hallucination spirals" by validating state at each checkpoint.

### 🛡️ Standards Gate
Documented standards are enforced automatically at pre- and post-implementation checkpoints using three severity tiers:
-   **must**: Blocks the workflow.
-   **should**: Warning in the trace.
-   **may**: Informational.

### 🧭 Philosophies
Beyond standards (the *what*), GLaDOS tracks **philosophies** (the *why*) — high-level design principles like "All APIs should be RESTful" or "Zero-downtime deployments are non-negotiable." Core philosophies are enforced as blocking constraints.

### 👁️ Silent Capture
The `pattern_observer` module passively logs implicit standards and philosophies as they emerge during normal work — user corrections, repeated patterns, and explicit statements get captured in `glados/observations/` for later review.

### 🧩 Modular Architecture
Logic is shared across workflows using Modules (`src/modules/`).
-   **Observability**: Standardized logging.
-   **Persona Context**: Review and operating persona management.
-   **Standards Gate**: Automated enforcement at checkpoints.
-   **Pattern Observer**: Passive implicit-pattern detection.
-   **Capabilities**: Introspects available tools (Browser, DB, MCPs).

---


GLaDOS installs directly into your project, creating a `glados/` directory for configuration and command scripts.

### Basic Installation

To install (or update) GLaDOS, run the install script and specify your environment:

**Claude Code:**
```bash
./bin/glados-install.sh --mode claude
```
*Installs commands to `.claude/commands`.*

**Antigravity (IDE):**
```bash
./bin/glados-install.sh --mode antigravity
```
*Installs workflows to `.agent/workflows`.*

**Gemini CLI:**
```bash
./bin/glados-install.sh --mode gemini
```
*Installs as a skill to `.gemini/skills/glados`.*

### The `glados/` Directory

Every installation scaffolds a `glados/` directory in your project root:
-   `glados/PROJECT_STATUS.md`: The high-level state of your project.
-   `glados/personas/`: Custom personas (add your own here!).
-   `glados/overlays/`: Directory for local overlays to customize workflows.
-   `glados/standards/`: Documented coding and architectural standards.
-   `glados/philosophies/`: High-level design principles and agreements.
-   `glados/observations/`: Staging area for implicitly detected patterns.

### Updates & Overlays

To update your commands or ingest new local overlays from `glados/overlays/`, run:

```bash
./bin/glados-update.sh --ingest-overlays
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

1.  **Full Onboarding** (recommended):
    Run `/adopt-codebase`. This orchestrates the full brownfield sequence: structural analysis, standards extraction, philosophy discovery, and mission alignment.
2.  **Or, Step by Step**:
    1.  Run `/review-codebase` to analyze your file structure and populate `PROJECT_STATUS.md`.
    2.  Run `/establish-standards` to extract tribal knowledge into `standards/` files.
    3.  Run `/mission` to ensure the agent understands the project's purpose.
3.  **Resume Work**:
    Run `/identify-bug` or `/plan-feature` to start contributing.

### Path C: Autonomous Mode
*Best for hands-off development.*

1.  **Ignite the Loop**:
    Run `autonomous_loop`.
2.  **Bootstrap**:
    -   **Empty Repo**: It will ask for your Vision and Success Criteria once, then take over.
    -   **Existing Repo**: It will read your `ROADMAP.md` and start executing the next active task.
3.  **Sit Back**:
    The agent will Plan, Spec, Implement, and Verify features in a continuous loop, answering its own questions based on your defined Mission and Standards.

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
| `/adopt-codebase` | Full brownfield onboarding sequence. |

### 2. The Development Loop
For every feature, follow this 4-step cycle:

1.  **`/plan-feature`**: Analyzes requirements, consults the Roadmap, drafts a high-level approach.
2.  **`/spec-feature`**: Refines the plan into a detailed `spec.md`. Triggers **Persona Review**.
3.  **`/implement-feature`**: Writes code based on the spec. Updates traces in `specs/`.
4.  **`/verify-feature`**: Runs tests, verifies against the spec, and updates the `walkthrough.md`.

### 3. Maintenance
| Command | Description |
| :--- | :--- |
| `/identify-bug` | Creates a reproduction plan before touching code. |
| `/plan-fix` | Lightweight planning for smaller issues. |
| `/implement-fix` | Targeted code changes. |
| `/retrospect` | Review recent work to improve `standards/` or process. |
| `/recombobulate` | Systematically clean up vibe debt, formalize patterns, audit standards. |
| `/consolidate` | Alias for `/recombobulate`. |

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
3.  **Personas** in `src/personas/` define agent roles.

Please ensure any new feature includes a corresponding Module or Persona if applicable to keep workflows DRY.
