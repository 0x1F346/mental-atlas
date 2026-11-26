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

## D-010 (2026-11-25) ElevenLabs adapter: direct mode by default, untested against the live API
- Context: The plan wants the adapter to hide whether the provider answers directly or by callback, and wants M2-T5 tested against a recorded response from a synthetic clip. Live calls need the owner's key and approval. The API reference documents an early-return mode (`webhook=true`) and a get-by-id endpoint, but not what that endpoint returns while work is in progress.
- Decision: The adapter supports two modes behind the same `submit`/`fetch` interface. `direct` (the default) sends one request and waits for the transcript. `poll` sends `webhook=true` and then asks for the transcript by id, reading any non-200 answer as "not ready". The test fixture `tests/recorded/elevenlabs_scribe_synthetic.json` was built by hand from the API reference, not recorded.
- Reason: `direct` uses only documented behaviour. In `direct` mode the worker does hold one connection open for the length of the transcription, which the plan wanted to avoid; `poll` removes that once it has been checked against the live API.
- Alternatives considered: A public webhook endpoint; rejected for V1 because local development has no public address.
- Approved by owner: not needed. The owner should run a live smoke test, replace the fixture with a recorded response, and then decide on `poll`. Note that the key-term list adds a 20% surcharge per the reference.

## D-011 (2026-11-25) Schema-constrained output uses structured outputs, not a forced tool call
- Context: The plan specifies schema-constrained output through tool definitions. The current Claude models (including the default, `claude-sonnet-5-5`) reject forced tool use, so a tool call can no longer be required.
- Decision: The tool schemas generated from the vocabulary are sent as a JSON schema in `output_config.format`. Numeric and length constraints that structured outputs does not accept are removed before sending and enforced in code. Requests are streamed. A declined request is retried on the provider's recommended fallback model (`fallbacks: "default"`), which `ATLAS_EXTRACTION_FALLBACKS=false` turns off. Extraction effort defaults to `medium` (`ATLAS_EXTRACTION_EFFORT`).
- Reason: It is the supported way to guarantee schema-valid output on these models. Checked against the Anthropic API documentation on 2026-11-25.
- Alternatives considered: `tool_choice: auto` with a strict tool, which does not guarantee a call is made.
- Approved by owner: not needed. The adapter is tested against a stub client only; no live call has been made.

## D-012 (2026-11-25) Extraction writes nothing until the commit stage
- Context: The plan runs statements first, then concepts, and requires each source to commit statements, nodes, relationships and evidence in one transaction.
- Decision: The pipeline has separate `statements`, `concepts`, `commit`, `embed` and `place` stages. The first two keep their validated output on their `runs` row; `commit` inserts everything in one transaction. Statements carry the statements run's id and concepts, relationships, evidence, aliases and match decisions carry the concepts run's id. Reprocessing is offered from `statements` or `concepts` (and the ingestion stages), not from `commit` onwards.
- Reason: It keeps the all-or-nothing commit while letting a failed concepts stage be retried without repeating statement extraction.
- Alternatives considered: Writing statements as soon as pass A finishes.
- Approved by owner: not needed

## D-013 (2026-11-25) Extraction rules added in code
- Context: The plan asks for code-level validation and leaves several cases open.
- Decision: (1) A concept that breaks the diagnosis rule is dropped and counted, never moved to unsorted. (2) A Feeling linked as `explicit` is downgraded to `implied` when none of its name's words appear in the cited statement, so an unnamed feeling cannot be stored as stated. (3) A therapist's statement is always kind `observation`; an owner's statement proposed as `observation` is sent to repair. (4) A Person named "me", "I" or similar is the owner's existing node. (5) Concept mentions may carry `also_called`, so two names for one person in the same window become aliases of one node. (6) An Event matches an existing one only when both have the same date and their involved people do not disagree; an undated event never matches. (7) Relationships that fail validation after repair are dropped and counted; only concepts go to unsorted.
- Reason: Each closes a way for an inference to be stored as if someone had said it, or for two things to be merged into one.
- Alternatives considered: Leaving these to the prompt.
- Approved by owner: not needed. Rule 6 means the same event mentioned without a date in a later source becomes a second node; the owner may want this relaxed after the first real session.

## D-014 (2026-11-25) Embedding provider not chosen; local hashed embedder is the default
- Context: Choosing the embedding provider is an open question for the owner.
- Decision: `atlas/providers/embeddings_http.py` speaks the common hosted embeddings request shape, configured by `ATLAS_EMBEDDING_BASE_URL`, `ATLAS_EMBEDDING_API_KEY`, `ATLAS_EMBEDDING_MODEL` and `ATLAS_EMBEDDING_DIMENSION`. Until those are set, live mode uses the local hashed bag-of-words embedder, which sends nothing outside but only recognises shared words. Vector columns have no fixed dimension, and every vector stores its model and dimension.
- Reason: The pipeline must run before the owner chooses, and re-embedding is cheap at this scale.
- Alternatives considered: Picking a provider for the owner.
- Approved by owner: no, awaiting the owner's choice. Matching by similarity is weak until a real embedding model is configured; exact-name and alias matching are unaffected.

## D-015 (2026-11-25) Evaluation: oracle run in place of the live scorecard
- Context: M3 is done when the scorecard meets its targets. `make eval` calls the paid model, which needs the owner's approval.
- Decision: `make eval-fake` replays each fixture's expected output through the real pipeline and scores the result. It meets every target, which shows the pipeline stores what a correct model would produce and that the scorecard measures it. In a live run, concept precision is judged by a model call per stored concept; in the oracle run it counts a stored concept as supported when it matches an expected one.
- Reason: It verifies everything that can be verified without a paid call.
- Alternatives considered: None available without the owner.
- Approved by owner: no. The M3 exit condition is not met until the owner runs `make eval` and the live scorecard meets its targets. Prompts `statements_v1`, `concepts_v1`, `match_v1` and `speaker_roles_v1` have never been run against a live model.

## D-016 (2026-11-25) Backups for the local set-up; deployment left to the owner
- Context: M6-T2 asks for a scheduled database dump and versioning on the bucket. Whether V1 is hosted (M6-T1) is an open question for the owner.
- Decision: `make backup` dumps the local Postgres into a git-ignored directory and deletes dumps older than 30 days; `make restore-check` loads the newest dump into a scratch database and prints row counts; `make bucket-versioning` turns on object versioning with a lifecycle rule that expires earlier versions and delete markers after 30 days. Scheduling is one cron or launchd line, given in `scripts/backup.sh`; nothing is installed on the owner's machine. No deployment work (container images, managed Postgres, HTTPS, secrets) has been done.
- Reason: These are the parts of M6-T2 that do not depend on the hosting decision. The 30-day expiry keeps the plan's promise that deleted data leaves the backups.
- Alternatives considered: Installing a launchd job; rejected as a change to the owner's machine that was not asked for.
- Approved by owner: not needed for the scripts. M6-T1 awaits the owner's decision.

## D-017 (2026-11-25) Independent review of the backend: what was fixed and what was left
- Context: After M5 a separate reviewer read the API, database, retraction and pipeline code. It found no way for one user to reach another's rows, and eleven defects elsewhere.
- Decision: Fixed, each with a regression test in `tests/test_review_fixes.py` unless noted:
  1. A job cancelled by a reprocess or retraction while its stage ran used to finish anyway and queue the next stage. The runner now re-checks the job under a row lock and discards the stage's work. Confirming an upload locks the source row.
  2. Two sources matched before either committed created duplicate concepts, and a concept deleted between matching and commit broke the commit. The commit now reuses a same-named concept created since matching, and sends the source back to the concepts stage when a reused concept has gone.
  3. A diagnosis was accepted on the model's own `explicit` label. It now also needs the speaker's verbatim quote to contain a word of the diagnosis name, and a rejected diagnosis is never salvaged into unsorted.
  4. The "did the speaker name this feeling" check read the model's restatement and matched inside words. It now reads the quote only and matches whole-word openings.
  5. A retracted diagnosis could make every later commit that touched it fail. It now stays retracted and is not offered as a match.
  6. A node with no run was treated as system-created, and deleting a source clears run ids, so an ordinary node could become permanent. Migration 0003 adds `nodes.is_system` (no dedicated test; covered by the existing retraction tests).
  7. An event used only as another relationship's context was deleted on retraction. It is now kept (no dedicated test).
  8. Deleting a source now also deletes the derived audio and raw transcript by their fixed keys, whether or not a database row records them (no dedicated test).
  9. A job that kept outliving its lease was reclaimed forever; it is now failed after `ATLAS_JOB_MAX_ATTEMPTS`. A failed heartbeat no longer ends the heartbeat thread.
  10. Sign-in attempts are counted before the password check, and idle entries are dropped from the limiter.
  11. Database engines hide bound parameters, and unhandled API errors are caught before the server can log their message.
- Left as they are:
  - Matching by similarity (not by exact name) can still create a duplicate when two sources are processed at once. The plan assumes one source at a time; duplicates can be merged.
  - A stage that uploads a file after its source was deleted leaves that file in storage until the bucket's lifecycle rule or a manual clean-up removes it.
  - The sign-in limit is keyed on the connecting address. Behind a reverse proxy every client shares one address, so this needs the proxy's forwarded address before hosting.
  - The logger accepts any single token of up to 80 characters as a code, so a one-word name passed as a field would be logged. No call site does this.
  - `ATLAS_COOKIE_SECURE` defaults to false for local HTTP and must be set when serving over HTTPS.
- Reason: The fixed items could corrupt the atlas, store an inference as a statement, or block deletion. The others are bounded and belong with the hosting work.
- Alternatives considered: A unique constraint on concept names, rejected because two different people or events may share a name.
- Approved by owner: not needed

## D-018 (2026-11-25) The map is a WebGL force-directed graph in a space theme
- Context: The plan's settled decision for the map is six fixed regions with drawn borders, rendered in SVG, with a concept keeping its position once placed. The owner asked to replace the renderer with a WebGL force-directed graph: dark space theme, glowing points sized by evidence and coloured by life area, each life area a gravity well with no drawn borders, positions seeded from `map_positions`, ambient drift, particles along links, a pulse on recently seen nodes, a dim flicker for hypotheses, and on click a camera ease with neighbours revealed and the rest dimmed.
- Decision: `web/src/map/ForceGraphRenderer.tsx` replaces `SvgMapRenderer.tsx` behind the same `MapRenderer` interface. `/map`, `/nodes/{id}`, the evidence endpoints, the evidence panel, the filters and the backend layout are unchanged.
  - Library: `react-force-graph-3d` 1.29.2 (released 2026-09-29) on `3d-force-graph` 1.80.2 (released 2026-11-05) and `three` 0.187. The repository is not archived and both packages had releases in the last two months. The single 3D package is used, not the `react-force-graph` umbrella, which also pulls in the VR and AR builds. It is loaded on demand because it is large.
  - Positions: each node starts at its saved map position. A force pulls it to its life area's anchor (the gravity well) and a second, stronger one back to its own saved place, so the learned geography survives. What the simulation does is not saved; `map_positions` stays the record.
  - Relationships are still hidden until a landmark is selected, because `/map` carries no edges. Selecting one adds its links, with particles, and a link force spreads its neighbours around it.
  - Accessibility and tests: the canvas is mirrored by a visually hidden list of buttons, one per landmark and one per shown relationship. With no WebGL the list is shown instead. `prefers-reduced-motion` turns off drift, pulse, flicker, particles and camera easing.
- Reason: Owner's instruction.
- What this gives up from the plan, for the owner to accept or ask to restore:
  - Region borders and coastlines are no longer drawn. The stored region polygons are unused by the renderer.
  - A landmark no longer sits at exactly its saved position; it settles near it.
  - Concept type is no longer shown on the map (no icons); it is in the panel and the filters.
  - Stated and observed look the same on the map. Only a hypothesis is marked, by its flicker; the panel still labels all three.
  - Fading by age is replaced by a pulse on landmarks seen within a month of the newest appearance.
- Not verified: frame rate with hundreds of landmarks, and rendering on a real GPU. It was looked at in headless Chromium with software rendering only.
- Alternatives considered: `react-force-graph-2d`, which draws on a 2D canvas and is not WebGL.
- Approved by owner: yes (requested)

## D-019 (2026-11-26) The map is flat, and node shape depends on concept type
- Context: The owner asked for the graph to be 2D instead of 3D, and for Person nodes to be small hearts.
- Decision: The force simulation runs in two dimensions (`numDimensions={2}`) and the view cannot be turned: dragging moves it and the wheel zooms. It is still drawn with WebGL through `react-force-graph-3d`, which keeps the glow, the particles and the camera ease from D-018. Node shape comes from `TYPE_SHAPES` in `web/src/map/space.ts`: `person` is a heart and every other type is a round point. Adding a shape for another type is one entry there plus a texture.
- Reason: Owner's instruction. Staying on the same library avoids a second rewrite; `react-force-graph-2d` draws on a 2D canvas and would lose the additive glow.
- Alternatives considered: Switching to `react-force-graph-2d`.
- Approved by owner: yes (requested)

## D-020 (2026-11-26) Test data can be uploaded as JSON
- Context: The owner asked for a way to upload test data as a JSON blob with arrays such as `person` and `feeling`, to fill the atlas without recordings or a model.
- Decision: `POST /sources` accepts `test_data`, and the upload form has a "Test data" mode. The blob has one array per core concept type, plus optional `relationships`; the format and its checks are in `backend/atlas/pipeline/test_data.py` and a full example is `evals/fixtures/synthetic/test_data.example.json`. It becomes an ordinary source with a new `import` pipeline stage run by the worker:
  - Every item gets statements and evidence, generated when no `quotes` are given, so each one still traces to a quote and computed fields still come from evidence. `status` chooses the voice: `stated` is the owner speaking, `observed` the therapist, `hypothesis` an implied link. `count` sets how many statements back it.
  - The blob is checked against the vocabulary before anything is stored: kinds, type-specific fields, relationship endpoints, and the diagnosis rule (a diagnosis cannot be a hypothesis).
  - Names match existing concepts by exact name or alias, so a blob can extend the atlas. "me" is the owner.
  - Retracting the source removes everything it added; "Extract again" re-runs the import.
- Reason: Owner's instruction. Going through a source and the worker keeps design rules 3 and 4 and the rule that only the worker writes to the atlas.
- Not changed: the vocabulary. A test-data source is stored with the existing kind `archive` and `metadata.test_data = true`, because adding a `test_data` source kind is a vocabulary change that needs the owner's approval. Say the word and it becomes its own kind.
- Alternatives considered: Inserting nodes directly with no evidence; rejected because nodes without evidence are retracted by the rules and would break click-through.
- Approved by owner: yes (requested)

## D-021 (2026-11-26) People are drawn as stars
- Context: D-019 drew Person nodes as hearts. The owner asked for stars instead.
- Decision: `TYPE_SHAPES` in `web/src/map/space.ts` maps `person` to `star`, a five-pointed star with the same glow, tint and sizing. The heart is kept as an available shape, unused.
- Reason: Owner's instruction.
- Alternatives considered: None.
- Approved by owner: yes (requested)

## D-022 (2026-11-26) Relationship lines are colour gradients, with no particles
- Context: D-018 drew relationships as thin lines with particles travelling along them. The owner asked to remove the moving particles and draw lines whose colour grades from the origin point to the connecting point.
- Decision: Each relationship of the selected landmark is a flat ribbon whose colour runs from the origin's life-area colour to the connecting point's. A hypothesis is drawn fainter; the selected relationship is drawn wider. No particles. The pulse on recently seen landmarks and the flicker on hypotheses are unchanged.
- Reason: Owner's instruction. A ribbon in the graph's plane is used instead of a GL line because GL lines are one pixel wide.
- Alternatives considered: three.js fat lines (`Line2`).
- Approved by owner: yes (requested)
