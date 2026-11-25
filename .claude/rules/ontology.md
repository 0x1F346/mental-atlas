---
paths:
  - "ontology/**"
  - "backend/atlas/domain/**"
---

# Vocabulary rules

- `ontology/atlas.yaml` is the single definition of the vocabulary. Enums, validation models, database check constraints, the extraction schema, TypeScript types and `docs/ONTOLOGY.md` are generated from it.
- Generated files are not edited by hand. Change `ontology/atlas.yaml` and run `make generate`.
- Any vocabulary change needs the owner's approval before it is made.
- A vocabulary change also needs a version bump in the file, a regenerate and a new migration.
- `noticed_by` and `status` are computed from evidence and never set by hand.
- The hypothesis rule and the diagnosis rule are enforced in code at commit time, not only in prompts.
