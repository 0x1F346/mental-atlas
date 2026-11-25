# Progress

## Now
- Milestone: M1 Vocabulary and database
- Current task: M1-T1
- Next step: Write `ontology/atlas.yaml` version 1 from the plan's data model.
- Blocked on: nothing. Unattended build authorised, see D-003.

## Milestones
- [x] M0 Foundations
- [ ] M1 Vocabulary and database
- [ ] M2 Ingestion
- [ ] M3 Extraction
- [ ] M4 Map layout and read API
- [ ] M5 Web map
- [ ] M6 First real session

## Tasks in the current milestone
- [ ] M1-T1: Write `ontology/atlas.yaml` with every type, kind, relationship and endpoint rule from this plan, as version 1.
- [ ] M1-T2: Write the generator and `make generate`. Add a CI check that generated files are current.
- [ ] M1-T3: Migrations for every table in the data model, the vector columns, and row-level security keyed on a per-session user setting. Seed one user and the six life areas.
- [ ] M1-T4: A database session helper that sets the user for each request and job. A test proves a second user cannot read the first user's rows.
- [ ] M1-T5: The commit-time rules module: computed fields, the hypothesis rule and the diagnosis rule, with unit tests.
- [ ] M1-T6: `retract_run` and `retract_source`, with tests that counts and dates are recomputed.
- [ ] M1-T7: Sign-in, sign-out, session cookie and `GET /auth/me`.

Done when the isolation test and rule tests pass, and a hand-built test graph can be inserted and retracted with nothing left behind.

## Milestone reports
### M0 Foundations (2026-11-25)
- `make dev` on the working tree: `GET /api/v1/health` returned `{"status":"ok"}` on :8000 and through the web proxy on :5173; the page served with the title "Mental Atlas".
- `make verify`: ruff, mypy, 9 backend tests and 1 web test passed.
- Not checked: a literal fresh clone, and the CI workflow's first run on GitHub (see the session log).

## Session log (newest first, keep the last 10)
### 2026-11-25
- Done: M0-T1 to M0-T5. Memory setup, repository skeleton, Compose with Postgres plus pgvector and MinIO, typed settings, content-safe logging, CI workflow. Decisions D-001 to D-005.
- Verified by: `make verify` (all passed) and a `make dev` smoke check with curl.
- Unfinished: nothing in M0.
- Next: M1-T1.

## Known issues
- `docs/plan/IMPLEMENTATION_PLAN.md` is a text extract of the PDF, not the owner's Markdown export (D-002).
- Setup step 8 is unconfirmed: the owner should run `/context all` (or `/memory`) in a new session and check that `CLAUDE.md` is listed.
- The Bash deny rules in `.claude/settings.json` block any shell command whose text names the local env file or `data/`, including heredocs. Write such files with the editor tools, not the shell.
