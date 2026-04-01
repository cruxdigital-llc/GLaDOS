# Structured Development Artifacts (SDA) Standard v1.0

*A tool-agnostic markdown format for tracking phased software development work.*

---

## 1. Purpose

This standard defines a minimal, human-readable, machine-parseable markdown format for organizing software development work into **trackable units** that progress through **phases**. It is designed to be:

- **Tool-agnostic**: Any agent, IDE, CI pipeline, or human can produce and consume conformant artifacts
- **Git-native**: All state lives in the repository as plain markdown — no external database required
- **Incrementally adoptable**: Projects can conform at different levels without all-or-nothing commitment

This document defines the **format**, not the **tooling**. Specific tools (frameworks, board viewers, CI integrations) implement *profiles* of this standard that map these generic concepts onto their own conventions.

---

## 2. Terminology

Keywords follow RFC 2119: MUST, MUST NOT, SHOULD, SHOULD NOT, MAY.

| Term | Definition |
|---|---|
| **Work Unit** | A self-contained directory representing a discrete piece of work (feature, bugfix, task) |
| **Phase** | A lifecycle stage that a work unit progresses through |
| **Roadmap** | A hierarchical, numbered list of planned work items with completion status |
| **Status Document** | A project-level summary of active work, known issues, and recent changes |
| **Claim** | A record of ownership over a roadmap item by a person or agent |
| **Profile** | A concrete mapping of this standard onto a specific tool's conventions |

---

## 3. Work Units

### 3.1 Structure

A work unit is a directory containing markdown files. The directory name MUST encode at minimum:

- A **date** in YYYY-MM-DD format
- A **human-readable identifier** in kebab-case ([a-z0-9]+(-[a-z0-9]+)*)

A profile MAY define additional name segments (e.g., a type prefix). The standard does not mandate a specific separator or segment order — only that date and identifier are recoverable by the profile's parser.

Example patterns (all valid, determined by profile):

    2026-04-01_user-authentication/
    2026-04-01_feature_user-authentication/
    feature/2026-04-01-user-authentication/

### 3.2 Phase Detection

Work units progress through an ordered sequence of **phases**. The standard defines phase detection as a concept but does not mandate specific phase names — profiles define those.

Phase MUST be determinable from the **presence and content of files** within the work unit directory. Specifically:

1. **File presence** — which files exist in the directory determines the minimum possible phase
2. **Completion markers** — checkbox state ([ ] vs [x]) within those files MAY advance the phase further
3. **Log markers** — the presence of specific entries in a trace/log file MAY indicate terminal phases

A profile MUST document:
- The ordered list of phases it supports
- The file-presence rules that map to each phase
- The priority order when multiple rules match (first match wins)

### 3.3 Required File: Trace Log

Every work unit MUST contain a trace log file (typically README.md) that records:

- When the work was initiated
- Key decisions made during the work
- Files created or modified
- Review or verification results

The trace log is the human-readable audit trail. It is also the mechanism for detecting terminal phases (e.g., a verification entry signals completion).

### 3.4 Checkpoint Files

Work units SHOULD contain files that represent discrete checkpoints in the development lifecycle. Common checkpoint types include:

| Concept | Purpose |
|---|---|
| **Requirements** | What needs to be achieved and why |
| **Plan** | High-level approach to achieving the requirements |
| **Specification** | Detailed technical design |
| **Task List** | Ordered, checkable implementation steps |

A profile defines which of these are required at which phase, and what the files are named. The standard only requires that:

- Checkpoint files MUST be markdown
- Task lists MUST use standard markdown checkbox syntax: - [ ] (incomplete) or - [x] (complete)
- The completion state of all checkboxes in a task list MUST be usable as a phase transition signal

### 3.5 Optional Metadata (Frontmatter)

Any file in a work unit MAY include YAML frontmatter for machine-readable metadata:

    ---
    priority: P1
    labels: [backend, auth]
    due: 2026-04-15
    custom_field: value
    ---

The standard defines no required frontmatter keys. Profiles MAY define required or recognized keys. Consumers MUST ignore unrecognized frontmatter keys.

---

## 4. Roadmap

### 4.1 Structure

A roadmap is a markdown file containing a hierarchical, numbered list of planned work with completion checkboxes. It represents the project's backlog and progress at a glance.

The hierarchy MUST have exactly three levels:

    Phase -> Section -> Item

### 4.2 Grammar

    ROADMAP     := HEADER PHASE+
    HEADER      := COMMENT? BLANK* TITLE BLANK
    TITLE       := "# " TEXT_TO_EOL
    COMMENT     := HTML_COMMENT
    PHASE       := PHASE_HEAD BLANK GOAL BLANK SECTION+
    PHASE_HEAD  := "## " PHASE_LABEL
    PHASE_LABEL := TEXT_TO_EOL (SHOULD include a sequential number)
    GOAL        := "**Goal**: " TEXT_TO_EOL
    SECTION     := SECTION_HEAD BLANK ITEM+
    SECTION_HEAD  := "### " SECTION_LABEL
    SECTION_LABEL := TEXT_TO_EOL (SHOULD include a hierarchical ID)
    ITEM        := "- [" STATUS "] " ITEM_BODY NEWLINE
    STATUS      := " " | "x"
    ITEM_BODY   := TEXT_TO_EOL (SHOULD begin with a hierarchical ID)

### 4.3 Item IDs

Items SHOULD have hierarchical IDs in the format {phase}.{section}.{item} (e.g., 1.2.3). IDs:

- MUST be unique within the roadmap
- SHOULD be sequential within their parent
- Are the primary key used by claim systems and board viewers

If a profile requires IDs (recommended), they MUST appear as the first token in ITEM_BODY.

### 4.4 Extraction

Each ITEM maps to a trackable card with:
- id — hierarchical ID (if present) or positional index
- title — item text (after ID)
- completed — true if STATUS == "x"
- section — parent section label
- phase — parent phase label

### 4.5 Example

    <!--
    SDA: v1.0
    -->

    # Roadmap

    ## Phase 1: Foundation

    **Goal**: Core platform infrastructure.

    ### 1.1 Authentication

    - [x] 1.1.1 Token generation
    - [ ] 1.1.2 OAuth integration

---

## 5. Status Document

### 5.1 Purpose

A status document provides a project-level view of what's actively being worked on, what's broken, and what recently changed. It is distinct from the roadmap (which is the plan) — the status document is the current state.

### 5.2 Required Sections

A conformant status document MUST contain these H2 sections:

| Section | Purpose |
|---|---|
| ## Current Focus | Active work items grouped by area, with checkbox completion status |
| ## Known Issues / Technical Debt | Unresolved problems and accumulated debt |
| ## Recent Changes | Timestamped log of completed work |

It SHOULD also contain:

| Section | Purpose |
|---|---|
| ## Project Overview | Brief description, mission link, current phase |
| ## Architecture | Tech stack and structural decisions |

### 5.3 Current Focus Format

    ## Current Focus

    ### 1. {Area Name}

    *Lead: {Person or Agent}*

    - [ ] **{Label}**: {Description}
    - [x] **{Label}**: {Description}

- Area sections MUST use numbered H3 headings
- Task lines MUST use checkbox + bold label + description format
- Lead lines are optional
- Sections titled "Backlog" or "Upcoming" SHOULD be treated as non-active by consumers

### 5.4 Recent Changes Format

    ## Recent Changes

    - 2026-04-01: Completed authentication module
    - 2026-03-28: Project initialized

Each entry MUST begin with an ISO 8601 date.

---

## 6. Claims

### 6.1 Purpose

A claims file records ownership of roadmap items. It enables coordination between multiple developers and/or agents working concurrently.

### 6.2 Grammar

    CLAIMS_DOC := COMMENT? BLANK* TITLE BLANK ENTRY*
    TITLE      := "# Claims" NEWLINE
    ENTRY      := "- [" STATE "] " ITEM_ID " | " CLAIMANT " | " TIMESTAMP RELEASE? NEWLINE
    STATE      := "claimed" | "released" | "expired"
    ITEM_ID    := /\d+\.\d+\.\d+/
    CLAIMANT   := /[^|\n]+/ (non-empty, no pipe characters)
    TIMESTAMP  := ISO_8601
    RELEASE    := " | " ISO_8601
    ISO_8601   := /\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z/

### 6.3 Lifecycle

    (new) -> claimed -> released
                     -> expired

- claimed — item is actively held
- released — voluntarily given up
- expired — revoked (TTL or operator action)

released and expired are terminal within a claim epoch. Re-claiming the same item creates a new entry.

### 6.4 Resolution

Active claims are resolved by processing entries top-to-bottom:
- claimed — sets active claim for that item ID
- released or expired — clears active claim for that item ID

Last entry wins for duplicates.

### 6.5 Validation Rules

| Rule | Severity | Condition |
|---|---|---|
| Title required | Error | Non-empty file missing # Claims heading |
| Entry format | Error | Line starting with - [ doesn't match entry pattern |
| Timestamp order | Error | Release timestamp is not after claim timestamp |
| Claimant format | Error | Empty or contains pipe character |
| Release timestamp | Warning | released/expired entry missing release timestamp |

---

## 7. Common Grammar

    TEXT_TO_EOL  := /[^\n]+/
    BLANK        := /^\s*$/
    NEWLINE      := "\n" | "\r\n"
    INTEGER      := /[1-9]\d*/
    HTML_COMMENT := "<!--" ... "-->" (may span lines)

All parsers MUST normalize CRLF to LF before processing. Trailing whitespace on any line MUST be ignored.

---

## 8. Versioning

Conformant documents SHOULD include the standard version in an HTML comment:

    <!--
    SDA: v1.0
    Last Updated: 2026-04-01
    -->

This enables consumers to adapt parsing as the standard evolves.

---

## 9. Conformance Levels

| Level | Requirements |
|---|---|
| **Minimal** | Work unit directories with correct naming, a trace log, and file-based phase detection |
| **Standard** | Minimal + conformant roadmap + status document |
| **Full** | Standard + claims file + YAML frontmatter metadata + version headers |

A consumer MUST support Minimal. A consumer SHOULD support Standard. A consumer MAY support Full.

A producer conforms to this standard if its output can be parsed by any conformant consumer at the declared level. A consumer conforms if it can parse any conformant producer's output at its supported level.

---

## 10. Profiles

A profile is a document that maps this standard onto a specific tool's conventions. A profile MUST declare:

1. **Directory naming pattern** — the exact regex for work unit directory names
2. **Phase names and detection rules** — ordered list with file-presence conditions
3. **File names** — which checkpoint files are used and what they're called
4. **File locations** — where the roadmap, status document, and claims file live in the repo
5. **Any extensions** — additional frontmatter keys, extra files, tool-specific markers

A profile MUST NOT contradict this standard. It MAY add requirements beyond it.

See: GLaDOS Profile v1.0 for the reference profile.
