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

## D-005 (2026-11-25) Local development topology and MinIO image
- Context: The plan asks for Docker Compose with Postgres plus pgvector and MinIO, and `make dev` starting the API, worker and web app. `minio/minio` is no longer pullable from Docker Hub or Quay.
- Decision: Compose runs only Postgres (`pgvector/pgvector:pg17`) and MinIO (`cgr.dev/chainguard/minio`). `make dev` starts them, applies migrations, then runs the API, worker and web app on the host. Postgres listens on host port 54329 and MinIO on 9100 to avoid clashing with local services. An init script creates the `atlas_app` role (no superuser, no BYPASSRLS) and an `atlas_test` database.
- Reason: Host processes reload quickly and need no image builds; container images for the app are M6-T1 work. The Chainguard build keeps MinIO as planned.
- Alternatives considered: Running everything in Compose; another S3-compatible server (SeaweedFS, RustFS).
- Approved by owner: not needed

## D-006 (2026-11-25) Vocabulary version 1: values the plan left open
- Context: The plan names some type-specific fields without listing their values, and names `ontology/atlas.yaml` as the one vocabulary file.
- Decision: Version 1 fills the gaps as follows. Group kinds: `family`, `employer`, `friend_circle`, `other` (optional). Event fields: `when` (date), `precision` (`day`, `month`, `year`, `approximate`, `unknown`), `occurrence` (`happened`, `planned`). Goal field `progress` (`open`, `reached`, `dropped`). Behaviour kind is `coping_tool` or empty. Trait kind is required. Source kinds: `therapy_session`, `voice_note`, `journal`, `archive`. The file also holds the shared enumerations (speaker roles, statement kinds, stance, basis, noticed-by, status, record state, life areas, source status) so that every constraint is generated from one place.
- Reason: Constraints and the extraction schema need closed sets. Each set has an escape value or is optional, so nothing the plan describes is excluded.
- Alternatives considered: Free-text fields; rejected because they cannot be checked.
- Approved by owner: not needed for creating version 1 from the plan; the owner should review these values, and any later change needs approval.

## D-007 (2026-11-25) Computed fields: details the plan left open
- Context: The plan defines `noticed_by` and `status` from explicit and implied links but does not say how a contradicting link, a third speaker, confidence or life-area weights are treated.
- Decision: Only a supporting explicit link counts as the speaker naming the thing; an explicit contradiction (a denial) adds nobody to `noticed_by`. An explicit link from a speaker with role `other` adds nobody. Node and relationship confidence is the highest confidence among supporting links. Each evidence link stores the life-area weights its mention gave (`evidence.life_area_weights`); a node's weights are the normalised average of those, so they can be recomputed after a retraction.
- Reason: A denial is the opposite of noticing, and marking it `stated` would hide exactly the gap three of the owner's questions ask about. Weights must be re-derivable for retraction to stay exact.
- Alternatives considered: Counting any explicit link as naming it.
- Approved by owner: not needed

## D-008 (2026-11-25) What retraction deletes and what it marks
- Context: Design rule 3 says retracting a run removes exactly what it wrote, M1 requires a test graph to be retracted "with nothing left behind", and M3 requires reprocessing to leave identical row counts. The ingestion section says a node left with no evidence is marked `retracted`.
- Decision: Retracting a run deletes the rows that run wrote: its statements, evidence, aliases, match decisions, and any node or relationship it created that has no evidence left. A node or relationship created by a different run that loses its last evidence is marked `retracted`, not deleted. A surviving node whose creating run is retracted is re-attributed to the run of its earliest remaining evidence. Nodes the system creates (the owner's Person node, the therapist) have no run and are never retracted. Retracting a source deletes the source row and everything that hangs from it, and returns the storage keys to delete.
- Reason: This satisfies the three exactness requirements and still uses the `retracted` state where a row belongs to another run's history.
- Alternatives considered: Marking everything `retracted`; rejected because reprocessing would then grow the tables.
- Approved by owner: not needed

## D-009 (2026-11-25) Accounts and sign-in tables
- Context: The plan asks for server-side sessions and row-level security on every table, but sign-in has to find a user before any user is set.
- Decision: A `sessions` table holds a hash of each cookie token. Two `SECURITY DEFINER` functions, `atlas_login_lookup` and `atlas_session_lookup`, are the only way to read across users, and each returns one exact match. The seeded user has an unusable password until `python -m atlas.cli set-password` is run.
- Reason: Keeps the application role unable to bypass row-level security while still allowing sign-in.
- Alternatives considered: A second, privileged database role for the API.
- Approved by owner: not needed
