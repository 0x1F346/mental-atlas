# Mental Atlas

A personal atlas of the owner's mind, built from therapy recordings and writing.
Specification: `docs/plan/IMPLEMENTATION_PLAN.md`. Read the section you are
working on before changing code.

## State
- Current state and next task: `docs/PROGRESS.md`
- Decisions and deviations: `docs/DECISIONS.md`
- Vocabulary: `ontology/atlas.yaml` (readable copy: `docs/ONTOLOGY.md`)

## Session routine
- Start every session with /session-start.
- End every session, and before context is compacted, with /session-end.
- One task per commit. Prefix the message with the task id (M2-T3: ...).

## Commands
- make dev       start API, worker, web, Postgres, MinIO
- make verify    lint, types, tests, generated-file check; must pass before every commit
- make generate  regenerate code from the vocabulary and the API schema
- make migrate   apply migrations
- make eval      live extraction scorecard; costs money, ask first
- make eval-fake scorecard with expected output replayed; no outside call
- make e2e       browser tests against the local stack with fake providers
- make smoke     one live call per provider adapter; costs money, ask first

## Layout
- backend/atlas: api, domain (generated models, rules), db, pipeline, providers, graph
- web/src: map, sources, generated API client
- evals: synthetic fixtures and scorecard

## Working in this repository
- The Bash deny rules block any shell command whose text names the local env file or `data/`,
  heredocs included. Write such files with the editor tools.
- Tests use the `atlas_test` database; `make infra` must be running.

## Rules that must never be broken
1. Postgres is the only source of truth.
2. Every table has user_id and a row-level security policy.
3. Every atlas write carries a run_id. Retraction must stay exact.
4. Never change meaning in place. Add rows.
5. Never hand-edit generated files. Change ontology/atlas.yaml and run make generate.
6. Vocabulary changes need the owner's approval.
7. Every provider call goes through its interface. Tests use the fakes.
8. Pipeline stages are idempotent and versioned.
9. Never log, print or commit transcript text, quotes, or model input or output.
10. Never read data/ or .env. Use only invented fixtures.
11. AI inferences are stored and shown as hypotheses. The AI never creates a diagnosis.

## Scope
- Build V1 only (milestones M0 to M6). Do not build later phases.
- If the plan is silent, choose the simplest option that keeps later phases
  possible and log it in docs/DECISIONS.md.
- If the plan seems wrong, stop and ask the owner. Do not work around it.

## Ask the owner before
- Changing the vocabulary, the four layers or a settled decision
- Adding anything that must be run or paid for as a service
- Running make eval or any live provider call
- Deleting a migration or rewriting git history
