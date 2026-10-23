---
canon: <name>
version: <edition, revision or last-updated date>
retrieved: YYYY-MM-DD
source-sha256: <sha256>
drafted-from: recall
---

<!--
HOW TO WRITE A CANON DIGEST. Delete this comment when the digest is done.

This file is the only form of the work that agents read. They never fetch the
source during a run, so a principle that is not written here does not exist
for them.

Frontmatter
- canon: the entry's name, exactly as declared under `canon:` in glados.yaml.
- version: what "the current version" meant when you wrote this: an edition,
  a revision, or a post's last-updated date.
- retrieved: the date the source was last read for this digest.
- source-sha256: the SHA-256 of the page's response body, byte for byte as
  fetched (for example `curl -sL <url> | sha256sum`). URL sources only:
  delete the line for a book. Leave the placeholder if you cannot compute
  it: the steward pass records it, then compares against it.
- drafted-from: `recall` (the default) when the digest was written from
  memory, by an agent or a person; `source` when it was written or checked
  with the work in hand. A `recall` digest is advisory-only until a person
  checks it against the source and changes this field to `source`.

Principles
- One `## <principle-id>` section per principle. The id is kebab-case and
  stable: findings cite it as canon:<name>#<principle-id>, so renaming it
  breaks every citation.
- Each section has three parts: the principle in your team's words (about
  100 words, naming the section or chapter it comes from); **Ask:** the
  question a reviewer puts to a change; **Here, specifically:** where it
  applies in this project, and its exceptions.
- Pick the principles that change decisions in this codebase. Keep the whole
  digest under about 1,000 words. `glados doctor` flags longer ones.

Copyright
- Write in your own words. This is a summary for your team, not a copy.
- Cite section or chapter names, not page numbers.
- Quote at most one sentence from the work in the whole digest.
- Never reproduce the text, its examples or its figures.

An example section, from a digest of Robert C. Martin's Clean Architecture:

    ## dependency-rule

    Dependencies in the code run one way: from the outer layers (frameworks,
    the database, the web, the UI) toward the inner ones (business rules and
    use cases). Inner code never mentions anything an outer layer defines:
    no class, function or data format from there. When inner code needs an
    outer layer to do something, it declares an interface it owns, and the
    outer layer implements it. Data crosses the boundary in a shape the inner
    layer chooses. The business rules then survive a change of framework or
    storage, and can be tested without either. (From the chapter "The Clean
    Architecture".)

    **Ask:** Does any new import, type reference or data shape make an inner
    layer depend on an outer one?

    **Here, specifically:** `domain/` and `services/` never import from
    `web/` or `storage/`. Handlers convert requests into domain types before
    calling a service. Exception: the value types in `domain/types/` may be
    used by every layer.
-->

# <Title of the work>

## <principle-id>

<The principle, in your team's words. About 100 words. Name the section or
chapter it comes from.>

**Ask:** <The question a reviewer puts to a change.>

**Here, specifically:** <Where this applies in this project, and its
exceptions.>
