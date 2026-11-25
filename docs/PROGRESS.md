# Progress

## Now
- Milestone: M0 Foundations
- Current task: M0-T1 (done, awaiting the owner's review)
- Next step: After the owner approves the memory setup, start M0-T2 (repository skeleton, Makefile and runners).
- Blocked on: the owner's review of M0-T1, and the plan being saved as Markdown (see Known issues)

## Milestones
- [ ] M0 Foundations
- [ ] M1 Vocabulary and database
- [ ] M2 Ingestion
- [ ] M3 Extraction
- [ ] M4 Map layout and read API
- [ ] M5 Web map
- [ ] M6 First real session

## Tasks in the current milestone
- [x] M0-T1: Carry out the memory setup in "Instructions for Claude Code". Stop for the owner's review.
- [ ] M0-T2: Repository skeleton, Makefile, and lint, type-check and test runners for backend and web.
- [ ] M0-T3: Docker Compose with Postgres plus pgvector and MinIO. `make dev` starts the API, worker and web app.
- [ ] M0-T4: Typed settings, `.env.example`, and structured logging that cannot carry content.
- [ ] M0-T5: A CI workflow that runs `make verify`.

Done when a fresh clone runs `make dev` and serves a health endpoint and an empty page, and `make verify` passes.

## Session log (newest first, keep the last 10)
### 2026-11-25
- Done: M0-T1 memory setup: `CLAUDE.md`, four rule files, three skills, `.claude/settings.json`, `docs/PROGRESS.md`, `docs/DECISIONS.md`, `.gitignore`.
- Verified by: `git status` and a file listing after the commit. `make verify` does not exist yet (M0-T2). Setup step 8 (`/context all`) was not run; it is a command the owner types.
- Unfinished: Setup steps 1 and 8, see Known issues.
- Next: Owner's review, then M0-T2.

## Known issues
- The plan is at `docs/plan/IMPLEMENTATION_PLAN.pdf`, not `docs/plan/IMPLEMENTATION_PLAN.md`. `CLAUDE.md` and the session-start skill point at the `.md` path. The owner needs to export the doc as Markdown to that path. The PDF is not committed.
- Setup step 8 is unconfirmed: the owner should run `/context all` (or `/memory`) in a new session and check that `CLAUDE.md` is listed.
