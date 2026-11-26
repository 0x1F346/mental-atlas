# Progress

## Now
- Milestone: M6 First real session
- Current task: waiting for the owner (see "Needs the owner")
- Design restyle (D-023, D-024, D-025): done on branch `design/living-tissue`, four commits plus a queue fix; `make verify` and `make e2e` pass. Not yet merged.
- Next step: Merge the design branch once the owner agrees. Then the owner runs `make smoke` and `make eval`; prompts and thresholds are then tuned against the result.
- Blocked on: the owner. Every remaining step needs a paid live call, real data or a decision.

## Needs the owner
In order. Nothing below has been done.
1. Review what was built unattended: decisions D-001 to D-017 in `docs/DECISIONS.md`, especially D-006 (vocabulary values), D-008 (what retraction deletes), D-013 (extraction rules added in code) and D-017 (review findings left open).
2. Run `/context all` in a new session and confirm `CLAUDE.md` is listed (setup step 8).
3. Create a local env file from `.env.example` with the Anthropic and ElevenLabs keys and `ATLAS_PROVIDERS=live`. Claude Code cannot read that file.
4. Run `make smoke` (paid, invented material only). It is the first live call to either provider. `make smoke RECORD=1` also replaces the hand-built ElevenLabs test fixture with a recorded one.
5. Run `make eval` (paid). M3 is not complete until this scorecard meets its targets.
6. Choose an embedding provider (D-014). Until then similarity matching only recognises shared words.
7. Decide whether V1 is hosted (M6-T1). No deployment work has been done.
8. Confirm retention settings with ElevenLabs, Anthropic and the embedding provider.
9. Answer the plan's remaining open questions: sessions in English, any third voice, the clockwise order of life areas, the scorecard targets.
10. Upload one real session (M6-T3) and check 30 statements and 30 concepts (M6-T4).

## Milestones
- [x] M0 Foundations
- [x] M1 Vocabulary and database
- [x] M2 Ingestion
- [ ] M3 Extraction (built and merged; live scorecard not yet run, see D-015)
- [x] M4 Map layout and read API
- [x] M5 Web map
- [ ] M6 First real session

## Tasks in the current milestone
- [ ] M6-T1: Deployment, if the owner wants V1 hosted: container images, managed Postgres, a storage bucket, HTTPS and secrets. Needs the owner's decision on hosting.
- [x] M6-T2: Backups: a scheduled database dump and versioning on the bucket. Local scripts only; scheduling is one cron line the owner adds (D-016).
- [ ] M6-T3: The owner uploads one real therapy session. Claude Code does not handle real data.
- [ ] M6-T4: The owner checks 30 random statements and 30 random concepts against the transcript, and records findings in `docs/DECISIONS.md` in general terms.
- [ ] M6-T5: Tune prompts and thresholds against the synthetic fixtures to address the findings.

Done when the owner can open any item on the map and read the quotes behind it. That is the V1 exit.

## Milestone reports
### Design restyle after M5 (2026-11-26), branch `design/living-tissue`
- The web app takes the "living tissue" design from `docs/design/` (D-023): tokens and self-hosted fonts, top bar, evidence panel, sources pages, and an SVG map renderer that supersedes D-018, D-019, D-021 and D-022 (D-024). What the restyle left out is in D-025.
- Verified: `make verify` (188 backend, 18 web tests) and `make e2e` (5 passed, fake providers), including landmark to quote to "Open in transcript" on the new map. Looked at by eye in headless Chromium at 1440×900 and 390×844 against the development atlas (136 invented concepts): the map fitted, zoomed to 196% and with a landmark selected; the panel; the sources list and an open source.
- Not verified: a timed transcript and the "Opened from the atlas" highlight by eye; a real GPU-less low-end machine; screen readers.

### Map renderer replaced after M5 (2026-11-25)
- The SVG map was replaced by a WebGL force-directed graph at the owner's request (D-018). `make verify` and `make e2e` pass with it. Checked by eye in headless Chromium with software rendering; not on a real GPU.

### M6 First real session (2026-11-25), in progress
- M6-T2: `make bucket-versioning` reported `Enabled`; `make backup` wrote a dump; `make restore-check` loaded it into a scratch database and the row counts matched the live database. Run against the local development database, which held no sources.
- An independent review of the backend found eleven defects; all eleven were addressed and five smaller points were left open (D-017).

### M5 Web map (2026-11-25)
- "The Playwright test passes": `make e2e` passed, 3 tests. `e2e/map.spec.ts` signs in, pastes the journal fixture, waits for Ready, opens the map, selects a landmark, reads its quote in the evidence panel and follows the link back to the transcript. Extraction in that test is the keyword fake, not a model.
- "Every hypothesis shows its label in the panel": component tests in `web/src/map/map.test.tsx` check the label for a hypothesis concept, a hypothesis relationship in the related list, and a relationship shown on its own; the API test checks every hypothesis landmark carries the label.
- Looked at by eye: screenshots of the map with the three fixtures loaded (31 concepts). Not looked at: audio playback from a quote in a real browser, behaviour with hundreds of landmarks, small screens.

### M4 Map layout and read API (2026-11-25)
- "Every active concept from the fixtures sits inside its home region": `test_every_active_concept_sits_inside_its_home_region` passes over all three fixtures, with no two landmarks closer than the minimum gap and the owner at the centre.
- "Adding a second source moves no existing landmark": `test_adding_a_second_source_moves_no_existing_landmark` passes (a landmark moves only if its home area changed).
- Reprocessing a source recreates its concepts and places them afresh; their positions can differ from before. Concepts that survive never move.

### M3 Extraction (2026-11-25), exit condition NOT fully met
- Built: M3-T1 to M3-T8. Fixtures, harness, pass A, pass B, embedding and shortlist, matching with the decisions log, the commit transaction, reprocess and retract.
- "Processing the same source twice leaves identical row counts": met. `test_processing_the_same_source_twice_leaves_identical_row_counts` passes for reprocessing from both `statements` and `concepts`.
- "The scorecard meets its targets": not verified. `make eval` needs the paid model and the owner's approval. `make eval-fake` (expected output replayed through the real pipeline) meets every target; that checks the pipeline and the scorecard, not the prompts or the model.
- Never exercised against a live service: the Claude adapter, all four prompts, the ElevenLabs adapter, a hosted embedding model.

### M2 Ingestion (2026-11-25)
- Browser (`make e2e`): the invented two-voice recording `evals/fixtures/synthetic/audio/two_voice_session.m4a` was uploaded through the signed link to MinIO, converted by ffmpeg, and reached a six-segment transcript with the therapist and owner roles correct; pasted text reached two segments.
- Limit of that check: transcription used the fake transcriber, whose script matches the recording. No live ElevenLabs call has been made (D-010).
- Killed worker: `test_a_worker_killed_mid_stage_resumes_that_stage_on_restart` and `test_an_expired_lease_lets_another_worker_take_the_job` pass. A real process kill was not performed.

### M1 Vocabulary and database (2026-11-25)
- Isolation: `tests/test_db_isolation.py` passes (a second user cannot read, change or delete the first user's rows; a session with no user sees nothing; the app role cannot bypass row-level security).
- Rules: `tests/test_rules.py` passes (computed fields, hypothesis label, diagnosis rule).
- Retraction: `tests/test_retraction.py` passes; the hand-built graph in `tests/support.py` is inserted and retracted and every table returns to its starting row count.

### M0 Foundations (2026-11-25)
- `make dev` on the working tree: `GET /api/v1/health` returned `{"status":"ok"}` on :8000 and through the web proxy on :5173; the page served with the title "Mental Atlas".
- Not checked: a literal fresh clone. CI passed on `main` for the M1, M2 and M3 merges; later runs were not checked when this was written.

## Session log (newest first, keep the last 10)
### 2026-11-26
- Done: the design restyle in four commits on `design/living-tissue` (tokens, fonts and top bar; evidence panel; sources pages; SVG map renderer). Decisions D-023, D-024, D-025. The owner approved superseding D-018, D-019, D-021 and D-022 and answered the brief's open questions: fonts self-hosted, no "soon" labels, an icon for every type with a shared colour for the eleven minor ones, six type chips plus "More", "Inferred" kept.
- Also fixed: jobs were queued with the host clock but claimed against the database clock, so with Docker's clock about 2 ms behind, `drain()` stopped early and 14 to 18 pipeline tests failed. `run_after` now comes from the database clock, with a regression test. This is the likely cause of the intermittent failure listed under Known issues before.
- Corrected: PROGRESS.md did not mention D-019 to D-022, which git shows were merged on 2026-11-26; they are now superseded by D-024.
- Verified by: `make verify` before each commit (last run: 188 backend, 18 web tests, lint, types, generated-file check), `make e2e` (5 passed) after the owner stopped a leftover worker from 2026-11-25. Screenshots in headless Chromium.
- Unfinished: merging the branch into `main`.
- Next: merge the branch. Then the owner's M6 steps.

### 2026-11-25
- Done: M0-T1 to M0-T5, M1-T1 to M1-T7, M2-T1 to M2-T8, M3-T1 to M3-T8, M4-T1 to M4-T5, M5-T1 to M5-T5, M6-T2, and the fixes from an independent backend review. Decisions D-001 to D-017. This was one unattended session across all milestones, which the owner authorised (D-003); the plan's one-milestone-per-session rule was not followed.
- Verified by: `make verify` (168 backend tests, 13 web tests, lint, types, generated-file check, all passed), `make e2e` (3 passed), `make eval-fake` (every target met), `make restore-check` (passed).
- Unfinished: M3's live scorecard, M6-T1, M6-T3, M6-T4, M6-T5. See "Needs the owner".
- Next: the owner's steps above, then M6-T5.
- Departures from the working rules: several tasks were committed together where they shared one module (M2-T2/3/4/6/7, M3-T3 to T8, M4-T3 to T5, M5-T1 to T5); each commit message lists its tasks.

## Known issues
- No prompt, and neither provider adapter, has been run against a live service (D-010, D-011, D-015).
- No embedding provider is configured (D-014); similarity matching uses a local word-hash embedder.
- `docs/plan/IMPLEMENTATION_PLAN.md` is a text extract of the PDF, not the owner's Markdown export (D-002).
- `test_a_failed_stage_is_recorded_and_can_be_retried_alone` failed once in about twenty runs before 2026-11-26. Probably the queue clock bug fixed that day (jobs queued on the host clock, claimed on the database clock); not seen since, but not proven.
- A worker can hang in a blocking call and then ignore SIGTERM, because it checks its stop flag only between jobs. One from 2026-11-25 survived until 2026-11-26 (probably a connection opened before Docker restarted). Before `make e2e`, check `pgrep -fl atlas.worker` for strays.
- Audio playback from a quote has only been exercised through component tests, not with a real recording in a browser.
- The map has room for a few hundred landmarks at the current spacing. Beyond that, placement falls back to overlapping positions, and it will need a spacing or zoom-level change in phase 2.
- On a phone, selecting a landmark with many relationships labels every neighbour, which crowds the small map. Phones were not in the design.
- An undated event mentioned again in a later source becomes a second node (D-013, rule 6).
- The Bash deny rules in `.claude/settings.json` block any shell command whose text names the local env file or `data/`, including heredocs. Write such files with the editor tools.
- Points left open by the backend review are listed in D-017.
