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

## D-002 (2026-11-25) Plan saved as extracted text
- Context: The plan was delivered as `docs/plan/IMPLEMENTATION_PLAN.pdf`. `CLAUDE.md` and the session-start skill read `docs/plan/IMPLEMENTATION_PLAN.md`.
- Decision: `IMPLEMENTATION_PLAN.md` is a machine text extract of the PDF (pypdf, layout mode) inside a text fence. The PDF is committed beside it and is authoritative.
- Reason: Sessions need a greppable plan at the documented path, and a hand transcription could silently change the specification.
- Alternatives considered: Waiting for the owner's Markdown export; rejected because the owner asked for unattended work. The owner can replace the file with a real export at any time.
- Approved by owner: not needed

## D-003 (2026-11-25) Unattended build authorised
- Context: The plan stops for the owner's review after M0-T1 and at the end of each milestone, and has the owner merge milestone branches.
- Decision: On 2026-11-25 the owner authorised Claude Code to commit, push and merge without stopping. Milestone branches are merged into `main` by Claude Code once the milestone's "Done when" checks pass, and a report is written to `docs/PROGRESS.md` instead of stopping.
- Reason: Owner's instruction.
- Alternatives considered: None.
- Approved by owner: yes
- Still requires the owner: live provider calls and anything paid (`make eval`, `make smoke`), real data (M6-T3, M6-T4), vocabulary changes, deployment (M6-T1), and the remaining open questions in the plan.

## D-004 (2026-11-25) Deny rules anchored to the project root, with Bash rules
- Context: The plan's settings template uses `Read(./data/**)`, which the permissions documentation anchors to the current directory, and Read rules do not cover every shell command.
- Decision: `.claude/settings.json` uses the root-anchored forms `Read(/.env)`, `Read(/.env.local)`, `Read(/data/**)` and adds Bash deny patterns for commands that name `.env`, `.env.local` or `data/`.
- Reason: The block must hold when a session starts in a subdirectory. The Bash patterns are best-effort; a script that opens the file itself is not caught, so rule 10 in `CLAUDE.md` still applies.
- Alternatives considered: Sandboxing; left for the owner.
- Approved by owner: yes
