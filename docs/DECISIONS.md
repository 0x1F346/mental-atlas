# Decisions

Append only. Decisions already made in the plan are not repeated here.
Never edit an earlier entry. Add a new one that supersedes it.

Entry format:

    ## D-NNN (YYYY-MM-DD) Title
    - Context:
    - Decision:
    - Reason:
    - Alternatives considered:
    - Approved by owner: yes / not needed

## D-001 (2026-11-25) Milestone branch names
- Context: The plan gives each milestone its own branch but does not name them.
- Decision: Branches are named `m<N>-<slug>`: `m0-foundations`, `m1-vocabulary-database`, `m2-ingestion`, `m3-extraction`, `m4-map-layout`, `m5-web-map`, `m6-first-session`.
- Reason: Matches the task-id prefix used in commit messages and sorts in build order.
- Alternatives considered: Committing directly to `main`; rejected because the owner reviews and merges each milestone.
- Approved by owner: not needed
