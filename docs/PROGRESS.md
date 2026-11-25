# Progress

## Now
- Milestone: M4 Map layout and read API
- Current task: M4-T1
- Next step: Region shapes with seeded borders.
- Blocked on: nothing for M4 and M5. The owner must run `make eval` (paid) to close M3, see D-015.

## Milestones
- [x] M0 Foundations
- [x] M1 Vocabulary and database
- [x] M2 Ingestion
- [ ] M3 Extraction (built and merged; live scorecard not yet run, see D-015)
- [ ] M4 Map layout and read API
- [ ] M5 Web map
- [ ] M6 First real session

## Tasks in the current milestone
- [ ] M4-T1: Region shapes with seeded borders, stored as layout version 1.
- [ ] M4-T2: The placement algorithm, with tests for determinism, no overlaps and pinned existing landmarks.
- [ ] M4-T3: The layout stage in the pipeline.
- [ ] M4-T4: `GraphStore` with an in-memory implementation.
- [ ] M4-T5: `GET /map`, the node and evidence endpoints, and the media link.

Done when every active concept from the fixtures sits inside its home region, and adding a second source moves no existing landmark.

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

### M2 Ingestion (2026-11-25)
- Browser (`make e2e`, 2 passed): the invented two-voice recording `evals/fixtures/synthetic/audio/two_voice_session.m4a` was uploaded through the signed link to MinIO, converted by ffmpeg, and reached a six-segment transcript with the therapist and owner roles correct; pasted text reached two segments.
- Limit of that check: transcription used the fake transcriber, whose script matches the recording. No live ElevenLabs call has been made (D-010); `tests/test_elevenlabs.py` exercises the adapter against a hand-built response.
- Killed worker: `test_a_worker_killed_mid_stage_resumes_that_stage_on_restart` and `test_an_expired_lease_lets_another_worker_take_the_job` pass. A real process kill was not performed.
- `make verify`: 104 backend tests and 2 web tests passed.

### M3 Extraction (2026-11-25), exit condition NOT fully met
- Built: M3-T1 to M3-T8. Fixtures, harness, pass A, pass B, embedding and shortlist, matching with the decisions log, the commit transaction, reprocess and retract.
- "Processing the same source twice leaves identical row counts": met. `test_processing_the_same_source_twice_leaves_identical_row_counts` passes for reprocessing from both `statements` and `concepts`.
- "The scorecard meets its targets": not verified. `make eval` needs the paid model and the owner's approval. `make eval-fake` (expected output replayed through the real pipeline) meets every target; that checks the pipeline and the scorecard, not the prompts or the model.
- Never exercised against a live service: the Claude adapter, all four prompts, the ElevenLabs adapter, a hosted embedding model.
- `make verify`: 139 backend tests and 2 web tests passed.

## Session log (newest first, keep the last 10)
### 2026-11-25
- Done: M3-T1 to M3-T8 (see the M3 report for what is unverified). Decisions D-011 to D-015.
- Done earlier the same day: M2-T1 to M2-T8. Providers and fakes, job queue and worker, source API, media, ElevenLabs adapter, text path, speaker roles, web pages, Playwright. Decision D-010.
- Done earlier the same day: M1-T1 to M1-T7. Vocabulary v1, generator, initial migration with row-level security, session helper, rules module, retraction, sign-in. Decisions D-006 to D-009.
- Done earlier the same day: M0-T1 to M0-T5. Memory setup, repository skeleton, Compose with Postgres plus pgvector and MinIO, typed settings, content-safe logging, CI workflow. Decisions D-001 to D-005.
- Verified by: `make verify` (all passed) and a `make dev` smoke check with curl.
- Unfinished: nothing in M0.
- Next: M4-T1.

## Known issues
- M3's live scorecard has not been run (D-015). No prompt has been run against a live model.
- No embedding provider is configured (D-014); similarity matching uses a local word-hash embedder.
- The ElevenLabs adapter is untested against the live API (D-010).
- `docs/plan/IMPLEMENTATION_PLAN.md` is a text extract of the PDF, not the owner's Markdown export (D-002).
- Setup step 8 is unconfirmed: the owner should run `/context all` (or `/memory`) in a new session and check that `CLAUDE.md` is listed.
- The Bash deny rules in `.claude/settings.json` block any shell command whose text names the local env file or `data/`, including heredocs. Write such files with the editor tools, not the shell.
