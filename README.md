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

### 🧩 Modular Architecture
Logic is shared across workflows using Modules (`src/modules/`).
-   **Observability**: Standardized logging.
-   **Capabilities**: Introspects available tools (Browser, DB, MCPs) to enhance execution.
-   **Persona Review**: Iterates through active stakeholders.

### ⚡ Split Lifecycles
Development is broken into discrete, verifying steps:
-   **Plan** → **Spec** → **Implement** → **Verify**.
This prevents "hallucination spirals" by validating state at each checkpoint.

---

## Installation

GLaDOS is installed via a shell script that injects the workflows into your project.

### 1. Antigravity Mode (Recommended)
Installs into `.agent/workflows` with YAML frontmatter for IDE integration.

```bash
./bin/glados-install.sh --mode antigravity
```

### 2. Direct Mode
Installs into `glados/` in your project root. Useful for manual inspection or custom setups.

```bash
./bin/glados-install.sh --mode direct
```

---

## Usage

Once installed, use the slash commands (or file references) to drive development.

### Project Setup
-   `/mission`: Define the `MISSION.md` and Audience.
-   `/plan-product`: create `ROADMAP.md` and `TECH_STACK.md`.
-   `/establish-standards`: Extract existing patterns into `standards/`.

### Feature Development
1.  `/plan-feature`: Analyze requirements, select Personas, update Roadmap.
2.  `/spec-feature`: Create detailed specs with Persona review.
3.  `/implement-feature`: Code the feature with iterative traceability.
4.  `/verify-feature`: Run tests and perform final architectural sign-off.

### Maintenance
-   `/identify-bug`: Create a reproduction case before fixing.
-   `/review-codebase`: Analyze legacy code.
-   `/retrospect`: Improve processes and standards.

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
