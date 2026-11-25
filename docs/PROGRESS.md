# Progress

## Now
- Milestone: M2 Ingestion
- Current task: M2-T1
- Next step: Provider interfaces and fakes.
- Blocked on: nothing. Unattended build authorised, see D-003.

## Milestones
- [x] M0 Foundations
- [x] M1 Vocabulary and database
- [ ] M2 Ingestion
- [ ] M3 Extraction
- [ ] M4 Map layout and read API
- [ ] M5 Web map
- [ ] M6 First real session

## Tasks in the current milestone
- [ ] M2-T1: Provider interfaces and fakes for `Transcriber`, `ExtractionModel`, `Embedder` and `BlobStore`.
- [ ] M2-T2: The job queue, the worker loop, the life cycle of a `runs` row, and stage retry.
- [ ] M2-T3: Source creation, signed upload, completion and the duplicate-file check.
- [ ] M2-T4: The media stage with ffmpeg.
- [ ] M2-T5: The ElevenLabs adapter, raw response storage and the segment builder. Test against a recorded response from a synthetic clip.
- [ ] M2-T6: The text source path.
- [ ] M2-T7: Speaker role assignment, the 0.9 threshold and the `needs_speaker_check` state.
- [ ] M2-T8: Web pages for sign-in, upload, the source list, and the source page with status, transcript, speaker check and swap.

Done when a synthetic two-voice recording uploaded in the browser reaches a transcript with correct roles, pasted text reaches segments, and a worker killed mid-stage resumes that stage on restart.

## Milestone reports
### M0 Foundations (2026-11-25)
- `make dev` on the working tree: `GET /api/v1/health` returned `{"status":"ok"}` on :8000 and through the web proxy on :5173; the page served with the title "Mental Atlas".
- `make verify`: ruff, mypy, 9 backend tests and 1 web test passed.
- Not checked: a literal fresh clone, and the CI workflow's first run on GitHub (see the session log).

### M1 Vocabulary and database (2026-11-25)
- Isolation: `tests/test_db_isolation.py` passes (a second user cannot read, change or delete the first user's rows; a session with no user sees nothing; the app role cannot bypass row-level security).
- Rules: `tests/test_rules.py` passes (computed fields, hypothesis label, diagnosis rule).
- Retraction: `tests/test_retraction.py` passes; the hand-built graph in `tests/support.py` is inserted and retracted and every table returns to its starting row count.
- `make verify`: 60 backend tests and 1 web test passed.
- For the owner to review: the vocabulary values in D-006, and the retraction semantics in D-008.

## Session log (newest first, keep the last 10)
### 2026-11-25
- Done: M1-T1 to M1-T7. Vocabulary v1, generator, initial migration with row-level security, session helper, rules module, retraction, sign-in. Decisions D-006 to D-009.
- Done earlier the same day: M0-T1 to M0-T5. Memory setup, repository skeleton, Compose with Postgres plus pgvector and MinIO, typed settings, content-safe logging, CI workflow. Decisions D-001 to D-005.
- Verified by: `make verify` (all passed) and a `make dev` smoke check with curl.
- Unfinished: nothing in M0.
- Next: M2-T1.

## Known issues
- `docs/plan/IMPLEMENTATION_PLAN.md` is a text extract of the PDF, not the owner's Markdown export (D-002).
- Setup step 8 is unconfirmed: the owner should run `/context all` (or `/memory`) in a new session and check that `CLAUDE.md` is listed.
- The Bash deny rules in `.claude/settings.json` block any shell command whose text names the local env file or `data/`, including heredocs. Write such files with the editor tools, not the shell.
