# Canon: the reference works your project follows

> Terms used here (*lane*, *outcome type*, *review panel*, *standards gate*)
> are defined in [concepts.md](../concepts.md).

**Canon** is the short list of books, papers and posts a team holds as
authoritative, such as Clean Architecture or Domain-Driven Design. Each work
gets a **digest**: a short summary in the repo, in the team's own words, with
one section per principle. Workflows read the digest at fixed points
(planning, shaping, speccing, verification and review), and findings cite a
principle by id:

```
canon:clean-architecture#dependency-rule
```

Canon advises. On its own it never blocks a merge. A principle blocks only
after the team adopts it as a standard (see [Weight and
precedence](#weight-and-precedence)).

GLaDOS ships no digests, only a template. Which works count, and what they
mean for your codebase, is your team's call.

## Declaring canon

Add a `canon:` block to `glados.yaml`. It is a map keyed by the work's name:

```yaml
canon:
  clean-architecture:
    source: "Robert C. Martin, The Clean Architecture (blog post, 2012)"
    url: https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html
    digest: product-knowledge/canon/clean-architecture.md
    applies-to: [plan-feature, shape, spec-feature, review-mr]
    seats: [philosophy, architect]
  domain-driven-design:
    source: "Eric Evans, Domain-Driven Design (2003)"
    digest: product-knowledge/canon/domain-driven-design.md
    seats: [architect, data-modeler]
```

| Key | Required | Meaning |
|---|---|---|
| `source` | yes | The citation a person would use to find the work. |
| `url` | no | Where the work lives online. Used for provenance and by steward's refresh. Agents never fetch it during a run. |
| `digest` | yes | The digest's path, relative to the repo root. It must stay inside the repo. By convention, `product-knowledge/canon/<name>.md`. |
| `applies-to` | no | The consult points that read this entry. Default: `[plan-feature, shape, spec-feature, verify-feature, review-mr]`. |
| `seats` | no | Which reviewers apply it: a standing lens or a persona. Default: `[philosophy]`. |

The name is kebab-case, and it is the first half of every citation.

`glados.yaml` is read with a restricted YAML subset. A few habits keep the
block parsing the way you meant it:

- Keep `canon:` a map keyed by name. A list of `- name: ...` items is a
  different shape and is rejected.
- Write `applies-to` and `seats` as one-line lists (`[a, b]`) or as block
  lists with one `- item` per line. Leave a key out to take its default; an
  empty list is rejected, because it would route the entry nowhere.
- Double-quote `source`. A space followed by `#` starts a comment, so
  `source: Team handbook #3` reads as `Team handbook`. Quote any value that
  contains ` #`.
- A `#` with no space before it, as in a URL fragment, is part of the value.

Canon is lane 2: the block is read live at run time. Editing it needs no
reinstall and never makes the compile stale. Digests are lane 3, read on
demand. Phase presets cannot set `canon:`; only your manifest can. Nothing
from the block or a digest is compiled into a workflow: the compiled text
only says how to consult canon.

## Writing a digest

Copy the template to the digest path and fill it in. A script install vendors
it at `.glados/src/templates/CANON.md`; the Claude Code plugin carries it at
`src/templates/CANON.md` under the plugin root. `install`, or the plugin's
`init`, creates an empty `product-knowledge/canon/` for digests.

A digest has frontmatter, then one section per principle:

```markdown
---
canon: clean-architecture
version: "2012-08-13"
retrieved: 2026-10-17
source-sha256: 3b1f...
drafted-from: source
---

# The Clean Architecture

## dependency-rule

Dependencies in the code run one way: from the outer layers (frameworks,
the database, the web, the UI) toward the inner ones (business rules and
use cases). ... (From the section "The Dependency Rule".)

**Ask:** Does any new import, type reference or data shape make an inner
layer depend on an outer one?

**Here, specifically:** `domain/` and `services/` never import from `web/`
or `storage/`. Exception: the value types in `domain/types/` may be used by
every layer.
```

| Field | Meaning |
|---|---|
| `canon` | The entry's name in `glados.yaml`. |
| `version` | What "the current version" meant when you wrote it: an edition, a revision, a post's last-updated date. |
| `retrieved` | The date the source was last read for this digest. |
| `source-sha256` | The SHA-256 of the page's response body, byte for byte as fetched (`curl -sL <url> \| sha256sum`). URL sources only. Leave the placeholder if you cannot compute it: steward records it, then compares against it. |
| `drafted-from` | `recall` when it was written from memory; `source` when someone wrote or checked it with the work in hand. The template starts at `recall`, so a digest nobody checked never passes for a sourced one. |

Each principle gets a `## <principle-id>` heading and three parts:

- **The principle**, in your team's words, in about 100 words. Name the
  section or chapter it comes from.
- **Ask:** the question a reviewer puts to a change.
- **Here, specifically:** where it applies in this codebase, and the
  exceptions your team has agreed.

Keep principle ids stable. Findings and standards cite them, and a rename
breaks every citation. Keep the whole digest under about 1,000 words: pick the
principles that change decisions in this codebase, not a chapter-by-chapter
summary.

A digest an agent drafted from memory says `drafted-from: recall`. Agents use
it, mark their citations "(drafted from recall)", and never let it raise a
finding above advisory. Memory of a book is often close and sometimes
confidently wrong, and nobody has checked this one yet. It stays that way
until a person checks it against the source and changes the field to
`source`.

## Why agents read digests, not URLs

Agents never fetch a canon URL during a run. They read the digest, for four
reasons:

- **Reviews have to be checkable.** Fresh-context reviewers, and the agents
  that try to refute a blocking finding, must read the same text as the agent
  that raised it. A fetched page can change between two reads, or render
  differently for two clients. A digest is a file at a commit.
- **Most books are paywalled.** A fetch returns an error or a login page.
- **A failed fetch invites invention.** A model that cannot read the source
  tends to fill the principle in from memory and cite it as sourced. With a
  digest, what the canon says is a file your team wrote and reviewed. A
  missing digest is reported as missing, never filled in.
- **Harnesses differ.** Some cannot fetch at all, and some only through a
  shell tool. A digest reads the same in every install.

## Keeping digests current

The `url` is for provenance and refresh. The weekly `steward` pass is the only
workflow that fetches it:

- For a URL source, steward fetches the page and compares the hash of the
  response body with `source-sha256`. When the hash changed, it reads the
  work beside the digest. If a principle the digest summarizes changed, it
  updates the digest, `version`, `retrieved` and `source-sha256` in its one
  cleanup MR, where a person reviews the change like any other. It keeps
  your **Here, specifically:** text and flags any the change may have made
  wrong. When only the page around the work changed (navigation, ads, a
  timestamp), or the hash did not change at all, the digest is left alone,
  except that once `retrieved` is over 180 days old it moves to today,
  with the new hash. A page that differs on every fetch costs a re-read,
  not a weekly edit.
- For a book, or a source it cannot fetch, steward reports the digest's age.
- It lists every `drafted-from: recall` digest as awaiting confirmation, and
  every declared digest that is missing. It never confirms a recall draft
  itself.

`glados doctor` reports, per entry, a digest that is missing (or is a
directory, or cannot be read), has no valid `retrieved:` date or one in the
future, was retrieved more than 180 days ago, is longer than about 1,000
words (frontmatter and HTML comments not counted), or was drafted from
recall. A template copied unedited reports its placeholder date and its
`recall` default. When the project uses `product-knowledge/canon/`, it also
says whether CODEOWNERS covers it: a digest decides what reviews hold a
change to, so give it the same owners as `glados.yaml`. Doctor never fails.

## Where canon is read

Each workflow that consults canon does it at one named **consult point**.
`applies-to` lists the consult points where an entry is read:

| Consult point | Where canon is read |
|---|---|
| `plan-feature` | choosing the approach; the plan names the principles it relies on |
| `shape` | the shape step of a project workflow, with its review and standards gate |
| `spec-feature` | the persona pass over the specification; the spec names the principles it relies on |
| `verify-feature` | the fresh evaluator verify-feature spawns |
| `review-mr` | the review panel on a merge request, including the reviews run-epic runs for its tickets |
| `review-codebase` | the architecture analysis of a codebase audit |
| `brunch` | the brunch reviewers |
| a step id from `steps:` | that project step, with its review and its gate (see [pipelines.md](pipelines.md)) |

Without `applies-to`, an entry is read at `plan-feature`, `shape`,
`spec-feature`, `verify-feature` and `review-mr`. An explicit list replaces
that default rather than adding to it, so to opt in to audits or the
roundtable, list the defaults you keep as well:
`applies-to: [plan-feature, shape, spec-feature, verify-feature, review-mr, brunch]`.
`review-codebase` and `brunch` are left out by default because judging a
whole codebase against every entry would bury the findings that matter. A
project step whose body cites a canon id reads that entry whatever its
`applies-to` says. When a pipeline asks for a review of a built-in step's
artifact (`review: fresh-agent` on `plan-feature`, say), the review belongs
to that step and reads what applies there.

Everything else is not a consult point, by design:

- implement-feature builds what the spec says, and the spec already names
  the principles it relies on; verification and review check the code
  against them.
- build-feature consults canon through its stages: each stage is a
  workflow of its own and reads what applies to it. run-pipeline does the
  same for the stages it nests, and consults canon itself only for `shape`,
  the project's own steps, and the reviews it runs of a built-in step's
  artifact (at that step's consult point).
- fix-bug's evaluator and standards gate do not consult canon. A bug fix
  restores agreed behaviour; it is not where a design is weighed.
- intent, adopt-codebase, address-review, retrospect, run-epic and steward
  do not consult canon either. Steward reads the block only to refresh
  digests.

`seats` decides who applies an entry. A seat is one of the five standing
lenses (`uat`, `adversarial`, `standards`, `philosophy`, `dead-code`) or a
persona, by file name: a library persona such as `architect`, or one of your
own in `product-knowledge/personas/`. Without `seats`, an entry goes to the
Philosophy lens; an explicit list replaces that default, so name
`philosophy` in it if the lens should keep the entry.

- An agent doing the work itself (planning, shaping, writing a spec, a
  persona pass, an audit) reads every entry that applies and presses each
  principle from the seat it names.
- A fresh agent (a panelist, an evaluator, a design reviewer) gets the digest
  paths for its seats, never a summary. A summary is the author's reading,
  and a fresh reviewer exists to make its own. Its brief also carries the
  rules for weight, recall drafts, citation and conflicts, copied verbatim,
  so a panelist that finds a departure from canon raises it as advisory
  like everyone else. An evaluator, or a design reviewer working alone,
  holds every seat, so it gets every entry that applies.
- On a review panel, an entry goes to each seat it names that is on the
  panel. If none is, it goes to the Philosophy lens; brunch seats personas
  only, so there every reviewer gets it.

## Weight and precedence

Canon is the weakest source a review cites. From strongest to weakest:

1. a decision the project has recorded;
2. standards;
3. philosophies;
4. canon.

A departure from canon is an `advisory` finding, and like every advisory it
has to name a consequence: a change in behaviour, in which defects a test
would catch, or in what someone has to work with when it fails. "This
departs from the book" is not a consequence.

To make a principle block, adopt it. Write a standard with `severity: must`,
or a philosophy with `weight: core`, that cites the canon id, and register it
in `product-knowledge/standards/index.yml` as usual:

```markdown
---
scope: [backend]
severity: must
keywords: [import, layer, dependency]
---
# Dependencies point inward

Adopts canon:clean-architecture#dependency-rule.

Code in `domain/` and `services/` never imports from `web/` or `storage/`.
Handlers convert requests into domain types before calling a service.
```

A departure is then a breach of that standard, and blocks like any `must`
breach; the finding cites both the standard and the canon id. The standards
gate classifies an unadopted canon principle as `advisory` too. Adoption is a
separate decision by a person, so the standard applies on its own text even
when the digest it cites was drafted from recall.

When canon disagrees with a higher source, the higher one wins and the
disagreement is not raised as a finding. It is an observation: an entry in
`product-knowledge/observations/` naming the canon id and what overrides it,
plus an `observation` outcome. review-mr commits its record to the
`glados/ledger` branch, never to the work's branch, so a conflict its panel
reports travels in the outcome only. A fresh agent lists conflicts under
**Canon conflicts** in its output (a panelist, as `canon-conflicts` in its
verdict object; an evaluator or a design reviewer, as a section of its
review file), and the workflow that spawned it files them. The steward pass
settles each one: change the standard or philosophy, or write the exception
into the digest's **Here, specifically:**, so it stops recurring.

## Copyright

A digest is a summary for your team, not a copy of the work.

- Write it in your own words.
- Cite section or chapter names, not page numbers.
- Quote at most one sentence from the work in the whole digest.
- Never reproduce the text, its examples or its figures.

Agents follow the same rule in what they write: they cite principle ids and
digest paths, and do not paste digest text into plans, specs, records or
comments. GLaDOS ships no digests of its own for the same reason: a summary of
someone's book is your team's to write.

## What the installer checks

`install`, `check` and `glados.py validate` reject a `canon:` block when:

- it is not a map keyed by name (a list of `- name:` items, for one);
- a name is not kebab-case;
- an entry is not a map, has a key other than `source`, `url`, `digest`,
  `applies-to` and `seats`, or lacks `source` or `digest`;
- `url` is present but empty or not a string;
- `digest` is a URL, an absolute path or the repo root, leaves the repo
  (`..`, or a symlink that points outside), or names a directory, a symlink
  loop or a broken link;
- `applies-to` is empty or names something that is not a consult point or a
  step declared under `steps:` (a pipeline's name is not one);
- `seats` is empty or names something that is not a standing lens, a library
  persona, or a persona in `product-knowledge/personas/` (a name that
  matches a persona file only by case is an error too: Linux CI would not
  find it).

Two digest problems are warnings, not errors: a digest file that does not
exist yet, so you can declare an entry before you write it, and a digest
path that matches the file on disk only by case, which opens on Windows and
macOS but not on a case-sensitive checkout. The assembly report lists each entry
(name, source, digest path, `applies-to`, `seats`, with defaults marked)
under `## Canon`. It never copies digest content.

## Before canon: a project persona

A project on a GLaDOS older than 2.5.0 can get most of this with no upgrade:
write the canon as a project persona and seat it on the review panel.

`product-knowledge/personas/clean-architecture.md`:

```markdown
---
type: review
priority_areas: [architecture]
standards_weight: ["*"]
---
# Clean Architecture Persona

**Role**: You review changes against the principles of Robert C. Martin's
Clean Architecture, as this team applies them. Your findings are advisory
unless a project standard adopts the principle.

**Responsibilities**:
-   Dependencies point inward: `domain/` and `services/` never import from
    `web/` or `storage/`.

**Key Questions to Ask**:
-   "Does any new import, type or data shape make an inner layer depend on
    an outer one?"
```

Then name it in `glados.yaml`:

```yaml
params:
  review-panel:
    personas: [clean-architecture]
```

It is seated on every review panel, plan-feature can seat it for a feature,
and spec-feature's persona pass reads it. It lacks what canon adds: citation
ids, the advisory-by-default weight (a persona's findings are classified like
any panelist's), steward's refresh and the doctor checks. When you upgrade,
move its principles into a digest, declare the entry with
`seats: [philosophy]` or the persona that should carry it, take the persona
off the roster, and delete its file: brunch seats every `type: review`
persona it finds, roster or not. Keep the file only if the canon entry
seats that persona by name.
