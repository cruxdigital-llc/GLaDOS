## The shape step

Shape sketches the code a change will add or alter as signatures without
bodies, so the structure is reviewed while changing it is still a text edit.
It works from the plan when an earlier step produced one, and from the brief
otherwise. It writes one file beside the run record, `<record>.shape.md`,
and nothing else.

| Section | What it holds |
|---|---|
| Units | Each new or changed module, type, function or handler: its path, its signature in the project's own language in a code block, and a one-line purpose. No bodies. |
| Changed signatures | Each existing signature that changes: `path:line`, the current form and the proposed one. |
| Dependency direction | Which unit depends on which, and the layer each one sits in. |
| Readers | For every new field or parameter, the unit that reads it. |
| Precedent | The existing unit each new one follows. |
| Left to spec | Semantics, invariants and error behavior: named here, decided in the spec. |

One unit, for example:

~~~markdown
### `src/billing/invoices.py` (new)
```python
def issue_invoice(order: Order, due_in_days: int) -> Invoice: ...
```
Issues one invoice for a paid order. Follows `src/billing/receipts.py`.
~~~

- **Readers is the cheapest place to drop a field.** *Verdicts and finding
  severities* asks a review to name the line that reads each new field; at
  shape time, name the unit. A field with no reader is dropped now, or its
  reader is named, before a spec, a test and a caller are built around it.
- **A change with no new or changed signatures** writes one line: "no new or
  changed signatures".
- **Never write stub files to the branch.** The shape lives only in its
  file. When implement-feature runs after a shape, pass it the shape with the
  spec: its first task lays the signatures down as stubs, and no stub
  survives to the MR.
- **Shape and spec split the decisions.** Shape decides names, types,
  placement and dependency direction. The spec decides semantics,
  invariants, payloads and errors. When spec-feature runs after a shape, pass
  it the shape with the plan: the spec builds on the shape and states any
  departure, and its persona pass does not reopen settled shape decisions.
- **Gate the shape.** After the review its `review:` setting asks for, this is
  the standards gate's shape checkpoint: audit the shape against the
  project's standards tree, as *Standards gate* sets out, and hand on only a
  shape that has cleared it.
