# Progress

## Now
- Milestone: M3 Extraction
- Current task: M3-T1
- Next step: Synthetic fixtures with expected output, before any prompt.
- Blocked on: nothing. Unattended build authorised, see D-003.

## Milestones
- [x] M0 Foundations
- [x] M1 Vocabulary and database
- [x] M2 Ingestion
- [ ] M3 Extraction
- [ ] M4 Map layout and read API
- [ ] M5 Web map
- [ ] M6 First real session

## Tasks in the current milestone
- [ ] M3-T1: Synthetic fixtures: two invented therapy transcripts and one journal entry, each with expected statements, concepts and relationships. Write these before the prompts.
- [ ] M3-T2: The evaluation harness, `make eval`, with the scorecard from "Testing and evaluation".
- [ ] M3-T3: Pass A with the quote check and repair.
- [ ] M3-T4: Pass B with schema validation, repair and the unsorted path.
- [ ] M3-T5: The embedding adapter and shortlist retrieval.
- [ ] M3-T6: Matching, with the decisions log.
- [ ] M3-T7: The commit transaction, using the M1 rules, followed by embedding.
- [ ] M3-T8: Reprocess and retract, wired to the API.

Done when the scorecard meets its targets, and processing the same source twice leaves identical row counts.

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

## Session log (newest first, keep the last 10)
### 2026-11-25
- Done: M2-T1 to M2-T8. Providers and fakes, job queue and worker, source API, media, ElevenLabs adapter, text path, speaker roles, web pages, Playwright. Decision D-010.
- Done earlier the same day: M1-T1 to M1-T7. Vocabulary v1, generator, initial migration with row-level security, session helper, rules module, retraction, sign-in. Decisions D-006 to D-009.
- Done earlier the same day: M0-T1 to M0-T5. Memory setup, repository skeleton, Compose with Postgres plus pgvector and MinIO, typed settings, content-safe logging, CI workflow. Decisions D-001 to D-005.
- Verified by: `make verify` (all passed) and a `make dev` smoke check with curl.
- Unfinished: nothing in M0.
- Next: M3-T1.

## Known issues
- `docs/plan/IMPLEMENTATION_PLAN.md` is a text extract of the PDF, not the owner's Markdown export (D-002).
- Setup step 8 is unconfirmed: the owner should run `/context all` (or `/memory`) in a new session and check that `CLAUDE.md` is listed.
- The Bash deny rules in `.claude/settings.json` block any shell command whose text names the local env file or `data/`, including heredocs. Write such files with the editor tools, not the shell.
