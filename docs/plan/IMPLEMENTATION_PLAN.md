# Mental Atlas: Implementation Plan

> Machine-extracted text of `docs/plan/IMPLEMENTATION_PLAN.pdf` (see D-002 in `docs/DECISIONS.md`).
> The PDF is authoritative where the two differ. Tables keep their column layout; `<!-- page N -->` marks PDF pages.
> In "Open questions for the owner" the first two items (relationship endpoint rules; Trait and statement kinds) are ticked as approved in the PDF.

```text
<!-- page 1 -->


  Nov 25, 2026   ·   @Trevor

Start here

This plan builds Mental Atlas V1: one therapy session uploaded, transcribed, turned into a
structured atlas and shown on a map. The foundations are designed to carry five later
phases without a rebuild.

It has two readers. The owner uses it to check scope and decisions. Claude Code uses it
as the build specification.

Handing it to Claude Code

  1. Create an empty Git repository named            mental-atlas      .
  2. Export this doc as Markdown and save it as            docs/plan/IMPLEMENTATION_PLAN.md             .
  3. Start Claude Code in the repository and give it this prompt: "Read
     docs/plan/IMPLEMENTATION_PLAN.md in full. Carry out the memory setup in the
     section 'Instructions for Claude Code', then stop for my review before writing product
     code."

How Claude Code should read it

     "Settled decisions" are fixed. Only the owner changes them.
     "Technology choices" are recommendations checked on 25 November 2026. Confirm
     versions and model names against live documentation before installing anything.
     "V1 build plan" is the only work in scope. Later phases are described so that V1 leaves
     room for them, and are not to be built yet.
     Where this plan is silent, choose the simplest option that keeps the later phases
     possible, and record the choice in        docs/DECISIONS.md        .

Product summary

Mental Atlas turns what a person says about their inner life into a structured map of their
mind that they can explore.

It takes recordings and writing, works out who said what, and builds a personal atlas of
people, situations, events, feelings, beliefs and behaviours, with the links between them.
Every item traces back to the exact words it came from.

Who it is for. The owner first, as a single user. It becomes a product for other people in
phase 6.










<!-- page 2 -->


Goals, in priority order

  1. Show recurring patterns.
  2. Get more out of therapy.
  3. Track change over time.
  4. Offer in-the-moment support through a conversational AI.

The questions it must answer. These six questions from the owner are the acceptance
test for the data model. Every type and relationship exists to serve at least one of them.

  1. What do I actually feel about a given situation?
  2. What tends to happen right before I pull away from someone?
  3. What am I not noticing in my pattern of pulling away?
  4. Where did this belief about myself come from, and who else holds it?
  5. What is causing me the most issues with my career right now?
  6. Where am I being unfair in my judgements of a particular person?

Non-goals

     It does not diagnose. A diagnosis enters the atlas only when the owner or the
     therapist states it.
     It does not replace therapy and is not a crisis service.
     It does not claim to know what the owner really feels. It offers hypotheses with the
     evidence attached.

Settled decisions

These are the outcomes of the scoping interview. They are fixed unless the owner
changes them.


  Topic                     Decision

  Audience                  The owner first, a product for others later. Every
                            record carries a user id from day one.

  Priorities                Patterns, then therapy value, then change over
                            time, then AI support.

  Inputs                    Therapy session recordings, voice notes, written
                            journal entries, existing archives.

  Signal captured           Words only in V1. Original media is kept so tone and
                            visual analysis can run over it later.











<!-- page 3 -->



  Topic                      Decision

  Therapist's speech         Captured as observations attributed to the
                             therapist. Speaker separation is required. The
                             therapist has consented to recording.

  Review                     Everything enters the atlas automatically. Every
                             entry has a source and a confidence, and can be
                             reversed.

  Data location              Cloud services are acceptable. Each provider sits
                             behind a swappable interface.

  Platform                   Web app first for input and viewing. Mobile later.
                             Desktop last, if ever.

  AI stance                  A mirror first. Coach and challenger modes later.
                             The atlas learns only from the owner's side of a
                             chat.

  Contradictions             Keep both sides and flag the tension as an insight.
                             Nothing is overwritten.

  Insight delivery           On demand only at first. Summaries, digests and
                             pre-therapy briefs later.

  Other people               Full profiles, modelled as the owner's view of each
                             person.

  Export                     Everything: graph, transcripts and raw files, in
                             open formats.

  Backlog                    Small: a few hours of recordings and a handful of
                             notes.

  Builder                    The owner, a senior engineer, working mostly
                             through AI coding agents.

  Technology                 Neo4j and ElevenLabs were suggestions. Each
                             component is chosen on merit.

  V1 boundary                One session uploaded and visible on the map, with
                             click-through from any map item to the quotes
                             behind it.

  Structure                  Four layers. A fixed vocabulary of 13 core types and
                             3 derived types. An unsorted pile for anything that
                             fits none. Only the owner changes types.













<!-- page 4 -->



  Topic                      Decision

  Lens                       Plain language at the core. Therapy frameworks are
                             optional overlays added later.

  Map                        Six fixed life areas as regions: Love, Family,
                             Friendships, Work, Body and health, Self. Emergent
                             themes are territories inside them. Patterns are
                             routes across them. Self sits in the centre.

  View priority              Map, then pattern cards, then network graph, then
                             timeline.

  Safety rules               AI inferences are always labelled as hypotheses.
                             The AI never assigns a diagnosis.


Phases and scope

V1 proves one path end to end. Each later phase adds to the same foundations.


  Phase      What it adds                                          Done when

  V1         One source end to end: upload,                        The owner uploads one real therapy
             transcription with speaker separation,                session, opens any item on the map and
             extraction into the fixed vocabulary,                 reads the quotes behind it
             storage across four layers, a map of six
             life areas, click-through to evidence

  2          All four input kinds and bulk import of               The backlog is in, one pattern card is
             the backlog. Themes as territories.                   backed by events from two or more
             Pattern cards, tensions and blind spots.              sources, and an export restores into an
             A view of the unsorted pile. Full export              empty instance

  3          Mirror chat that reads the atlas and                  A chat answer cites atlas items with
             writes the owner's turns back into it.                their evidence, and statements from
             Network graph view. Timeline view                     the chat appear in the atlas

  4          Summaries after each input, digests and               A weekly digest and a pre-session brief
             pre-therapy briefs. Coach and                         are produced on schedule
             challenger modes. Framework overlays

  5          Tone-of-voice and visual analysis over                Old recordings gain tone annotations
             stored media. Mobile app                              with no re-upload, and capture works
                                                                   from a phone














<!-- page 5 -->



  Phase     What it adds                                        Done when

  6         Multi-user product: sign-up, consent                A second user joins with fully isolated
            capture, privacy tiers, curated exports             data
            for third parties


In scope for V1

     Upload of one audio or video file, or pasted text.
     Transcription with speaker separation and timestamps.
     Assigning each voice a role: owner, therapist or other.
     Statement extraction with verbatim quotes.
     Concept and relationship extraction into the 13 core types, with misfits sent to the
     unsorted pile.
     Matching new concepts against existing ones, so the same thing is not stored twice.
     The map: six regions, one landmark per concept, and an evidence panel with quotes
     and audio playback from the moment of each quote.
     A source page showing processing status and the transcript.
     Retracting a source, which removes everything derived from it.
     Sign-in for a single user.

Out of scope for V1, with room left for it

     Generating themes, patterns, tensions and blind spots. The types exist in the schema
     and nothing writes them yet.
     Chat, export, bulk import, the other three views, scheduled insights, framework
     overlays, tone and visual analysis, mobile, multi-user.

A map built from one session will be sparse. V1 proves the pipeline and the trust model.
The atlas becomes useful in phase 2.

Technology choices

The stack is PostgreSQL as the single source of truth, a Python pipeline, a React web app,
ElevenLabs for transcription and Claude for extraction. Neo4j is not the main database;
the reasons are below.

























<!-- page 6 -->




  Concern                       Choice                                     Reason

  Transcription                 ElevenLabs Scribe v3, model id             Released 10 November 2026.
                                scribe_v3     , batch mode with            Word-level timestamps, speaker
                                speaker separation on                      labels, and a key-term list of up
                                                                           to 1,000 terms that can carry the
                                                                           names of people in the owner's
                                                                           life. source

  Extraction model              Claude through the Anthropic               Schema-constrained output
                                API. Default   claude-sonnet-5-            through tool definitions. Prompt
                                5 . Model ids live in                      caching keeps the full transcript
                                configuration                              in context cheaply across many
                                                                           calls.

  Embeddings                    A hosted text-embedding model              Choose the provider's current
                                behind an    Embedder     interface        general-purpose model at build
                                                                           time. Store the model name and
                                                                           dimension with every vector so
                                                                           re-embedding is possible.

  Database                      PostgreSQL 16 or later with the            Holds all four layers, the vectors
                                pgvector extension                         and the job queue in one
                                                                           transactional store.

  Graph queries and             Node and edge tables in                    One user's graph is small. See
  algorithms                    Postgres. Algorithms run in the            the Neo4j note below.
                                worker on an in-memory copy of
                                one user's graph

  File storage                  S3-compatible object storage.              Keeps original media for later
                                MinIO in local development                 tone and visual analysis.

  Backend                       Python 3.12 or later, FastAPI,             Best library support for the
                                SQLAlchemy 2, Alembic,                     pipeline and analysis work.
                                Pydantic 2                                 FastAPI emits an OpenAPI
                                                                           schema that generates the web
                                                                           client's types.

  Background jobs               A Postgres-backed job queue                No extra service to run. Volume
                                                                           is one source at a time.

  Media handling                ffmpeg                                     Extracts and normalises the
                                                                           audio track from any upload.

















<!-- page 7 -->



  Concern                      Choice                                    Reason

  Web app                      React, TypeScript, Vite. The map          Full control over the map's look.
                               is drawn in SVG with d3 modules           The renderer sits behind an
                               for zoom, layout and region               interface and can move to
                               shapes                                    canvas when item counts
                                                                         demand it.

  Sign-in                      One seeded user, password                 Real protection once deployed,
                               hashed with Argon2, server-               with no third-party dependency
                               side session cookie                       in V1.

  Running it                   Docker Compose locally. One               Enough for a single user.
                               container host plus managed
                               Postgres when deployed


Why Neo4j is not the main database

     The graph is small. A year of weekly sessions is estimated at about 10,000 statements
     and a few thousand concepts. That fits in memory many times over.
     Evidence and concepts must be written together. A concept without its quotes, or
     quotes pointing at nothing, breaks the trust model. One Postgres transaction
     guarantees this.
     The future product is many small, isolated graphs, one per user. Postgres row-level
     security handles that directly.
     One store means one backup, one export path and one thing to run.

Neo4j would add a concise language for path queries, built-in graph algorithms and a
visual browser. The plan keeps that option open: all graph reads go through a                    GraphStore
interface, and phase 3 includes a decision point on adding Neo4j as a read-only copy
rebuilt from Postgres.

On ElevenLabs. It is the transcription provider. The vendor reports the lowest speaker-
labelling error of the models it tested, but those are its own benchmarks. Milestone 2
checks the result on a real session, and the           Transcriber       interface allows a swap.

On the vector space. Statements and concepts are embedded from V1. V1 uses the
vectors to spot duplicates. Phase 3 uses the same vectors for chat retrieval.

Considered and set aside. Ready-made knowledge-graph memory frameworks own the
extraction step and the schema. Those are the two parts this project needs to control, so
the pipeline is built directly.

















<!-- page 8 -->

Architecture

The system has five parts: a web app, an API, a worker that runs the pipeline, Postgres and
object storage. Three outside services are reached through interfaces.


  Part                 Responsibility

  Web app              Upload, source pages, the map and the evidence
                       panel.

  API                  Sign-in, sources, map and evidence endpoints,
                       signed media links. It never calls an AI provider
                       inline.

  Worker               Runs the pipeline stages as background jobs. It is
                       the only part that calls AI providers and the only
                       part that writes to the atlas.

  Postgres             All four layers, vectors, the job queue and the run
                       log.

  Object storage       Original media, extracted audio and raw provider
                       responses.

  Providers             Transcriber     , ExtractionModel      , Embedder     and
                        BlobStore    . Each has one real adapter and one
                       fake for tests.


How one source flows through

  1. The owner uploads a file or pastes text. The browser sends a file straight to object
     storage through a signed link.
  2. The API records the source and queues a processing job.
  3. The worker extracts and normalises the audio.
  4. The worker transcribes it with speaker separation.
  5. The worker assigns each voice a role.
  6. The worker extracts statements, each tied to a verbatim quote.
  7. The worker extracts concepts and relationships from the statements.
  8. The worker matches new concepts against existing ones.
  9. The worker commits statements, concepts, relationships and evidence in one
     transaction.
10. The worker embeds the new statements and concepts.
11. The worker places new concepts on the map and saves their positions.










<!-- page 9 -->


12. The web app shows progress, then the map. Clicking an item loads its quotes and
     plays the audio from that moment.

Design rules. These nine rules are what keep later phases possible. Claude Code must not
break them.

  1. Postgres is the only source of truth. Everything else can be rebuilt from Postgres and
     object storage.
  2. Every row carries a      user_id    . Row-level security is switched on in the first migration.
  3. Every write to the atlas carries the id of the run that produced it. Retracting a run
     removes exactly what it wrote.
  4. Meaning is never changed in place. New evidence adds rows. Contradictions add
     rows.
  5. The vocabulary is defined in one file. Database constraints, validation models, model
     prompts and web types are generated from it.
  6. Every outside provider sits behind an interface with a fake implementation.
  7. Pipeline stages are idempotent and versioned. Reprocessing a source replaces its
     earlier output.
  8. Raw provider responses are kept, so later improvements can re-derive results without
     paying for transcription again.
  9. Transcript text, quotes and model output never go to logs or third-party monitoring.

Data model

The atlas has four layers. Each layer points to the one beneath it, so any item on the map
traces back to a quote and a moment in a source.


  Layer              Holds                                           Written by

  1. Sources         Recordings, texts, transcripts,                 Ingestion
                     speakers, segments

  2.                 Single things said, each with a                 Statement extraction
  Statements         speaker, a date and a verbatim quote

  3. Concepts        Typed nodes, typed relationships                Concept extraction, and analysis
                     and the evidence links that tie them            jobs from phase 2
                     to statements

  4. Regions         Life areas, themes and map positions            Seed data, layout, and analysis jobs
                                                                     from phase 2













<!-- page 10 -->


Core types

A node is a recurring concept, not an occurrence. "Dread" is one Feeling node however
often it appears. Each appearance is recorded as an evidence link and, where relevant, as
membership of an Event.


  Type           Meaning                                            Type-specific fields

  Person         Someone in the owner's life, as the                Relationship to the owner
                 owner sees them. The owner is also a
                 Person, flagged      is_self

  Group          A set of people: a family, an employer,            Kind
                 a friend circle

  Situation      An ongoing circumstance that could                 Start, end
                 change or end

  Event          One dated occasion, past or planned                When, precision, happened or
                                                                    planned

  Feeling        An emotion                                         None

  Sensation      A bodily sensation                                 Body area

  Belief         A standing conviction about oneself, a             None
                 person or the world. Judgements of
                 people are Beliefs

  Behaviour      Something a person does                            Kind:  coping_tool      or none

  Need           What a feeling or behaviour seeks or               None
                 protects

  Value          What matters to a person                           None

  Goal           Something being worked towards                     Open, reached or dropped

  Trait          A lasting characteristic of a person               Kind:  strength    , diagnosis    ,
                                                                    physical     or  other

  Role           A role or identity a person holds                  None


The test for the three that are easy to confuse: something that happens at a point in time
is an Event, a circumstance that could change or end is a Situation, and a lasting
characteristic of a person is a Trait.

Derived types. Pattern, Tension and Blind spot are written only by analysis jobs, starting
in phase 2. They are in the vocabulary from V1.









<!-- page 11 -->


Unsorted. Anything that fits no type is stored as type                 unsorted      with a suggested type
and a reason. It is kept off the map.

Relationships


  Name                     From                        To                            Meaning

  LED_TO                   Any core type               Feeling, Sensation,           One thing came right
                                                       Belief, Behaviour,            before, or brought on,
                                                       Event                         another. Records the
                                                                                     Event it happened in
                                                                                     when known

  OCCURRED_IN              Feeling, Sensation,         Event                         It showed up during that
                           Belief, Behaviour                                         event. Carries its order
                                                                                     in the event

  ABOUT                    Feeling, Belief,            Person, Group,                What it concerns. A
                           Need, Goal                  Situation, Event,             belief about oneself
                                                       Trait, Role                   points at the owner's
                                                                                     Person node

  CAME_FROM                Belief, Value,              Event, Person,                Where it originated
                           Behaviour, Need,            Group, Situation
                           Trait

  HOLDS                    Person                      Belief, Value, Goal,          That person holds it
                                                       Role

  HAS                      Person                      Trait, Need                   That person has it

  BELONGS_TO               Person                      Group                         Membership

  INVOLVES                 Event, Situation            Person, Group                 Who was part of it

  PART_OF                  Event, Role                 Situation, Group              An event inside a
                                                                                     situation, or a role inside
                                                                                     a group or situation

  SERVES                   Behaviour, Feeling,         Need                          It exists to meet that
                           Belief                                                    need

  HELPS                    Behaviour, Trait,           Goal, Need, Feeling,          It makes the target
                           Person, Situation,          Situation                     easier. Coping tools use
                           Belief                                                    this

















<!-- page 12 -->



  Name                    From                       To                           Meaning

  BLOCKS                  Behaviour, Trait,          Goal, Need, Value            It gets in the way
                          Person, Situation,
                          Belief

  CONFLICTS_WITH          Belief, Value, Need,       The same set                 The two pull against
                          Goal, Behaviour,                                        each other
                          Role

  SEEN_IN                 Pattern                    Event                        The pattern played out in
                                                                                  that event

  HAS_STEP                Pattern                    Any core type                An ordered step of the
                                                                                  pattern

  BETWEEN                 Tension                    Any node                     One side of the tension

  CONCERNS                Blind spot                 Any node                     What the blind spot is
                                                                                  about


The last four are used only from phase 2.

Who noticed it

Three of the owner's six questions ask about the gap between their own account and the
evidence. The model records that gap directly.

Every evidence link has a        basis   . It is explicit    when the speaker named the thing, and
implied     when the extractor inferred it from what was said. Two fields on every node and
relationship are computed from the evidence and never set by hand:

     noticed_by       lists any of  self   , therapist      and  ai  . An explicit link from the owner
     adds   self   . An explicit link from the therapist adds         therapist     . Any implied link adds
     ai  .

     status     is stated    when the owner has named it,           observed      when only the therapist
     has, and   hypothesis       when nobody has.

Two rules are enforced in code at commit time, not only in prompts:

     A hypothesis is always labelled as one, in the API and on the map.
     A Trait of kind    diagnosis     needs an explicit link from the owner or the therapist.
     Otherwise the commit rejects it.



















<!-- page 13 -->


Time

Each statement has two times.           said_at     is when it was said.     about_time       is when the
thing it describes happened, such as "childhood" or "last Sunday", stored as text with an
optional date range.

     Nodes and relationships carry          first_seen_at       , last_seen_at        and  evidence_count        ,
     all computed from       said_at     .
     Relationships carry       valid_from      and   valid_to      when a statement gives them, as in "I
     used to believe".
     A contradiction is an evidence link with stance             contradicts      . Both sides stay. Phase 2
     turns clusters of contradiction into Tension nodes.

Life areas

Six rows are seeded: Love, Family, Friendships, Work, Body and health, Self. Each node
gets a weight per area from its evidence. Its home is the area with the highest weight. If
no area holds at least half the weight, its home is Self. The owner's own Person node sits at
the centre of Self.

Tables

Every table has      id  (UUID),    user_id     and   created_at     .


  Table                           Layer      Main columns

  users                           -          email, password hash

  sources                         1          kind, title, occurred_at, status, language, metadata

  media_files                     1          source_id, storage_key, mime_type, bytes,
                                             duration_ms, sha256, role

  transcripts                     1          source_id, provider, model, raw_response_key,
                                             pipeline_version

  speakers                        1          source_id, provider_label, role, person_node_id,
                                             method, confidence

  segments                        1          source_id, speaker_id, idx, start_ms, end_ms,
                                             start_char, end_char, text






















<!-- page 14 -->



  Table                            Layer     Main columns

  statements                       2         source_id, segment_id, speaker_role, quote,
                                             quote_start_char, quote_end_char, start_ms,
                                             end_ms, text, kind, said_at, about_time_text,
                                             about_from, about_to, confidence, run_id,
                                             embedding

  nodes                            3         type, name, description, kind, attributes,
                                             life_area_id, life_area_weights, noticed_by, status,
                                             first_seen_at, last_seen_at, evidence_count,
                                             confidence, state, merged_into_id,
                                             schema_version, run_id, embedding

  node_aliases                     3         node_id, alias

  edges                            3         type, from_node_id, to_node_id, context_event_id,
                                             attributes, noticed_by, status, valid_from, valid_to,
                                             first_seen_at, last_seen_at, evidence_count,
                                             confidence, state, run_id

  evidence                         3         statement_id, target_kind, target_id, stance, basis,
                                             confidence, run_id

  resolution_decisions             3         run_id, proposed, candidate_ids, decision,
                                             matched_node_id, reason

  life_areas                       4         key, name, map anchor

  map_layouts                      4         version, parameters

  map_positions                    4         node_id, layout_id, x, y, placed_at

  runs                             -         source_id, kind, pipeline_version, prompt_version,
                                             schema_version, model, status, raw_output, usage,
                                             error, started_at, finished_at


In statements      , quote     is the verbatim excerpt and         text    is the same claim restated so it
makes sense on its own. In         nodes     and   edges   , state    is active    , merged     or retracted      .
Merges are soft, so they can be undone.

The vocabulary file

The vocabulary lives in one file,        ontology/atlas.yaml           . It lists node types, their fields and
kinds, relationship types with their allowed endpoints, and a version number.
















<!-- page 15 -->


A generator script reads it and writes five things: Python enums and validation models,
database check constraints, the schema handed to the extraction model, TypeScript
types, and    docs/ONTOLOGY.md        . To change the vocabulary, edit the file, raise the version,
run the generator and add a migration. Only the owner approves changes to this file.

Ingestion pipeline

Ingestion turns any upload into the same shape: a source with ordered segments, each
with a speaker and a position.

Upload

     Accepted inputs are audio files, video files, and pasted or uploaded plain text.
     The browser asks the API for a signed link, uploads straight to object storage, then
     confirms. The API records the file's hash, size and type.
     A file whose hash matches an existing source is refused, with a link to that source.
     The owner supplies the kind of source, a title, the date it happened, and optionally any
     names to expect.

Media

     The original file is stored untouched. Tone and visual analysis in phase 5 will read it.
     ffmpeg produces one derived mono audio file. Transcription and browser playback
     both use it.

Transcription

     The   Transcriber      adapter calls Scribe with speaker separation and word-level
     timestamps on. It passes the expected number of speakers when the API accepts
     one.
     The key-term list holds the names of Person and Group nodes already in the atlas, plus
     names given at upload.
     The adapter hides whether the provider answers directly or by callback. The worker
     never holds a connection open for a long file.
     The raw response is saved to object storage. The              transcripts      row points to it.
     Consecutive words from one speaker become one segment. A segment longer than
     about 1,200 characters is split at a sentence end.

Text sources

     No transcription step. Paragraphs become segments with character positions in place
     of timestamps.
     There is one speaker, with the role         self  .










<!-- page 16 -->


Speaker roles

     A voice note or journal has one speaker, the owner.
     For a therapy session, one model call reads the opening turns of each voice and
     assigns   self    and  therapist      with a confidence. The main signal is who asks the
     questions and who describes their own life.
     At a confidence of 0.9 or more, processing continues without a pause.
     Below 0.9, the source waits in        needs_speaker_check         . The source page plays a short
     clip of each voice and asks which one is the owner. This is the only manual step in the
     pipeline.
     Roles can be swapped later from the source page. A swap retracts the source's
     extraction runs and reprocesses from the statement stage.
     Each non-owner voice links to a Person node. The therapist's node is created once and
     reused.

This check exists because swapped roles would attribute the therapist's words to the
owner across a whole session. That is the most damaging single error the pipeline can
make.

Status

A source moves through         uploaded     , transcribing     , needs_speaker_check          when
required,   extracting     , placing     and   ready  , or stops at   failed   . Each stage writes a
runs    row. A failed stage can be retried without repeating the stages before it.

Retracting a source

Retracting removes the source's statements and evidence links. Any node or relationship
left with no evidence is marked         retracted    . Counts and dates on the rest are
recomputed. The media files are deleted from storage.

Extraction pipeline

Extraction runs in two passes: statements first, then concepts. Every concept is
grounded in a statement, and every statement in a verbatim quote that code can check.

Shared set-up

     The whole transcript goes into the prompt as cached context. Each call then works on
     a window of about 20 segments, with a 2-segment overlap. The full context helps
     interpretation, and the small window helps recall.
     A 50-minute session is roughly 7,500 words, estimated at 150 words a minute.
     Every call returns structured output against a schema generated from the vocabulary
     file.








<!-- page 17 -->


     The model, prompt version, schema version and raw output are saved on the                      runs
     row.

Pass A: statements

For each window the model returns statements. Each one has a segment id, a verbatim
quote, a restated version that makes sense on its own, a kind and an                 about_time     .

The kinds are     report    for what happened,       feeling     for how it felt,  reflection      for an
interpretation or realisation,      intention     for what the speaker means to do, and
observation       for a therapist's remark about the owner.

Code then checks each statement:

     The quote must be an exact substring of its segment, ignoring whitespace
     differences. A failure gets one repair attempt, then the statement is dropped and
     counted.
     The speaker role is copied from the segment. The model never chooses it.
     Statements from overlapping windows are de-duplicated by quote position.

The prompt tells the model to skip pleasantries and scheduling. A therapist's question
becomes a statement only when it carries an observation.

Pass B: concepts and relationships

For each window the model receives the window's statements, the vocabulary, and a
shortlist of existing concepts that might match. The shortlist comes from an embedding
search on the statements, plus every Person and Group node, plus concepts already
proposed for this source.

It returns three lists:

     Concept mentions: type, name, short description, kind, type-specific fields and life-
     area weights. Each cites its supporting statements with a stance and a basis. A
     mention that reuses a shortlisted concept gives that concept's id.
     Relationship mentions: type, both ends, the Event it happened in when known, and
     supporting statements with stance and basis.
     Unsorted items, each with a suggested type and a reason.

Naming rules in the prompt keep nodes consistent. Feelings are single plain words where
possible. Beliefs are full sentences in the holder's voice. Events are named by what
happened and when. People are named as the owner names them.

Code then validates the output:

     Types and relationship endpoints must match the vocabulary.
     Every mention must cite at least one statement from its window.









<!-- page 18 -->


     The diagnosis rule from the data model applies.
     A failed item gets one repair attempt with the error attached. If it still fails, a well-
     formed item goes to unsorted with the reason, and a malformed one is dropped and
     counted.

Matching against existing concepts

Each mention without a valid existing id goes through three steps:

  1. An exact match on the normalised name or an alias, within the same type, is accepted.
  2. Otherwise the nearest existing nodes of that type are fetched by embedding
     similarity.
  3. A best candidate at 0.90 or above is accepted. Between 0.75 and 0.90, one model call
     decides whether the two are the same concept. Below 0.75, a new node is created.

The two thresholds are starting values. They are tuned in the evaluation harness.

     People match only on a name or alias, or by a model decision that sees their
     relationship to the owner. Never on similarity alone.
     Events match only when the date and the people involved agree.
     Every decision is written to       resolution_decisions          . A match adds the new name as
     an alias.

When unsure, the pipeline creates a new node. Two nodes for one concept can be merged
later. One node standing for two concepts corrupts every count built on it.

Commit

Each source commits in one transaction:

  1. Insert statements, new nodes, new relationships and evidence links.
  2. Recompute       noticed_by     , status   , counts, dates and life-area weights for every node
     and relationship touched.
  3. Enforce the hypothesis and diagnosis rules.

If any step fails, nothing from the source is written.

After commit

     Embed new statements, using the restated text, and new nodes, using name plus
     description.
     Place new nodes on the map.

Reprocessing

















<!-- page 19 -->


Stages are keyed by source, stage and pipeline version. Running a stage again first
retracts the earlier run for that key. Prompts are versioned files under
backend/atlas/pipeline/prompts/                . Changing a prompt raises its version.

Models and cost

     The default model for both passes comes from configuration. Speaker roles and
     match decisions can use a smaller model.
     Prompt caching covers the transcript and the vocabulary block.
     Token counts are saved on each run, so the cost of a source is visible.
     Bulk import in phase 2 uses the provider's batch interface, which trades speed for a
     lower price.

The map

The map is the main view, and its geography is fixed so the owner can learn their way
around. Life areas never move, and a concept keeps its position once placed.

Geography

     The map is a disc inside a square of 1,000 by 1,000 units.
     Self is a circle at the centre. The other five areas are equal wedges of the ring around
     it, in a fixed clockwise order from the top: Love, Family, Friendships, Work, Body and
     health.
     Borders are roughened with seeded noise so they read as coastlines. The seed is
     fixed per user, so borders never change.
     Region shapes are computed once, stored in               map_layouts       and versioned.

Placing a concept

  1. Its region is its home life area.
  2. Its target point is the centre of its already-placed neighbours in that region. With no
     neighbours, the target is a seeded random point in the region.
  3. If a second life area holds 0.3 or more of its weight, the target is pulled towards that
     area's border.
  4. A short relaxation step moves only the new landmarks until none overlap. Existing
     landmarks are pinned.
  5. The position is saved to       map_positions      .

A position changes only when the concept's home area changes, or when the owner asks
for a full re-layout, which creates a new layout version. Layout runs in the worker, so every
device shows the same map. It is deterministic: the same inputs and seed give the same
positions.








<!-- page 20 -->


What V1 draws

     The six named regions.
     One landmark per active concept, with an icon for its type.
     Size grows with evidence count. A landmark fades as its last appearance gets older.
     The outline shows status: solid for stated, ringed for observed, dashed for hypothesis.
     Relationships are hidden until a landmark is selected, then drawn as lines to its
     neighbours.
     Zoomed out, the map shows regions and the largest landmarks. Zoomed in, it shows
     everything with labels.
     Filters by type, by who noticed it and by source.

Evidence panel

Selecting a landmark or a relationship line opens a side panel with:

     Name, type, description and a plain-language status line, such as "Hypothesis: nobody
     has said this directly."
     Who noticed it, when it was first and last seen, and how many times.
     Related items, grouped by relationship.
     Every quote behind it. Each shows the speaker, date, source, whether it supports or
     contradicts, and whether it was explicit or implied.
     A play button on each quote that starts the audio at that moment, and a link to the
     same point in the transcript.

Added in phase 2

     Territories. Themes are found by clustering the concepts inside each region. Each is
     drawn as a shaded area around its members.
     Stable themes. When clustering runs again, each new cluster is matched to the
     existing theme it overlaps most. At an overlap of half or more, it keeps that theme's id,
     name and colour.
     Routes. A pattern is drawn as a line through its steps in order, and may cross region
     borders.
     Markers for tensions and blind spots, and a tray for unsorted items.

Rendering

The API returns a map document: regions as polygons, landmarks as points with display
fields, and the relationships of one concept on request. Territories and routes join the
same document in phase 2.















<!-- page 21 -->


The web app draws the document in SVG, with d3 handling pan and zoom. The renderer is
one component behind a       MapRenderer     interface. Move it to canvas when measured frame
rates drop, expected somewhere past 2,000 visible landmarks.

Repository, API and conventions

One repository holds the backend, the web app, the vocabulary and the docs.

 mental-atlas/
   CLAUDE.md
   README.md
   Makefile
   docker-compose.yml
   .env.example
   .claude/
     settings.json
     rules/
     skills/
   docs/
     plan/IMPLEMENTATION_PLAN.md
     PROGRESS.md
     DECISIONS.md
     ONTOLOGY.md              generated
   ontology/
     atlas.yaml
     generate.py
   backend/
     pyproject.toml
     alembic/
     atlas/
       api/                   routes, sign-in, request and response schemas
       domain/                generated enums and models, commit-time rules
       db/                    table models, sessions, row-level security
 helpers
       pipeline/              stages, validators, prompts/
       providers/             transcriber, extraction model, embedder, blob
 store, fakes
       graph/                 GraphStore, in-memory graph, map layout
       worker.py
     tests/
   web/
     package.json
     src/
       api/                   generated client
       map/                   MapRenderer, evidence panel









<!-- page 22 -->



        sources/               upload, source page
    evals/
      fixtures/synthetic/      invented transcripts with expected output
      run_eval.py
    data/                      git-ignored; real recordings never enter the
  repository

API for V1. All paths sit under      /api/v1    , so a mobile client can rely on them later.


  Method and path                                          Purpose

  POST /auth/login      , POST /auth/logout       , GET    Session sign-in
  /auth/me

  POST /sources                                            Create a source. Returns a signed upload
                                                           link for a file, or accepts text directly

  POST /sources/{id}/complete                              Confirm the upload and queue processing

  GET /sources     , GET /sources/{id}                     List sources. Show one with its status by
                                                           stage

  GET /sources/{id}/transcript                             Segments with speakers and positions

  PUT /sources/{id}/speakers                               Set or swap speaker roles

  POST /sources/{id}/reprocess                             Run the pipeline again from a named stage

  DELETE /sources/{id}                                     Retract the source and everything derived
                                                           from it

  GET /map                                                 The map document

  GET /nodes/{id}                                          One concept with its neighbours

  GET /nodes/{id}/evidence         , GET                   The quotes behind a concept or
  /edges/{id}/evidence                                     relationship

  GET /media/{id}/link                                     A short-lived signed link for playback


Conventions

     Python: ruff for linting and formatting, strict type checking on              atlas/domain       and
     atlas/pipeline       , pytest.
     Web: TypeScript in strict mode, ESLint, Vitest, and one Playwright end-to-end test.
     make    targets:  dev   , test  , lint  , generate    , migrate    , eval   and   verify   . verify
     runs lint, types, tests and a check that generated files are current.












<!-- page 23 -->


     Migrations use Alembic. One migration per change. A merged migration is never
     edited.
     Ids are time-ordered UUIDs. Times are stored in UTC.
     Configuration is read once from environment variables into a typed settings object.
     .env.example       lists every variable with no secrets.
     API errors return a code and a message. They never include transcript text.
     Logs carry ids and counts only.
     Commits are small, one task each, prefixed with the task id, for example                  M3-T2:
     validate quote spans         .
     Each milestone has its own branch. The owner reviews and merges it at the
     milestone's end.

V1 build plan

V1 is seven milestones, built in order. Milestone 4 can start alongside milestone 3, using
the hand-built test graph from milestone 1.

M0: Foundations

     M0-T1: Carry out the memory setup in "Instructions for Claude Code". Stop for the
     owner's review.
     M0-T2: Repository skeleton, Makefile, and lint, type-check and test runners for
     backend and web.
     M0-T3: Docker Compose with Postgres plus pgvector and MinIO.                     make dev     starts the
     API, worker and web app.
     M0-T4: Typed settings,       .env.example      , and structured logging that cannot carry
     content.
     M0-T5: A CI workflow that runs         make verify      .

Done when a fresh clone runs          make dev     and serves a health endpoint and an empty page,
and   make verify      passes.

M1: Vocabulary and database

     M1-T1: Write    ontology/atlas.yaml          with every type, kind, relationship and endpoint
     rule from this plan, as version 1.
     M1-T2: Write the generator and         make generate       . Add a CI check that generated files
     are current.
     M1-T3: Migrations for every table in the data model, the vector columns, and row-level
     security keyed on a per-session user setting. Seed one user and the six life areas.








<!-- page 24 -->


     M1-T4: A database session helper that sets the user for each request and job. A test
     proves a second user cannot read the first user's rows.
     M1-T5: The commit-time rules module: computed fields, the hypothesis rule and the
     diagnosis rule, with unit tests.
     M1-T6:   retract_run      and   retract_source       , with tests that counts and dates are
     recomputed.
     M1-T7: Sign-in, sign-out, session cookie and           GET /auth/me      .

Done when the isolation test and rule tests pass, and a hand-built test graph can be
inserted and retracted with nothing left behind.

M2: Ingestion

     M2-T1: Provider interfaces and fakes for          Transcriber      , ExtractionModel       , Embedder
     and   BlobStore    .
     M2-T2: The job queue, the worker loop, the life cycle of a             runs   row, and stage retry.
     M2-T3: Source creation, signed upload, completion and the duplicate-file check.
     M2-T4: The media stage with ffmpeg.
     M2-T5: The ElevenLabs adapter, raw response storage and the segment builder. Test
     against a recorded response from a synthetic clip.
     M2-T6: The text source path.
     M2-T7: Speaker role assignment, the 0.9 threshold and the                needs_speaker_check
     state.
     M2-T8: Web pages for sign-in, upload, the source list, and the source page with status,
     transcript, speaker check and swap.

Done when a synthetic two-voice recording uploaded in the browser reaches a transcript
with correct roles, pasted text reaches segments, and a worker killed mid-stage resumes
that stage on restart.

The synthetic recording is an invented dialogue turned into audio with a text-to-speech
tool, using two different voices.

M3: Extraction

     M3-T1: Synthetic fixtures: two invented therapy transcripts and one journal entry,
     each with expected statements, concepts and relationships. Write these before the
     prompts.
     M3-T2: The evaluation harness,         make eval     , with the scorecard from "Testing and
     evaluation".
     M3-T3: Pass A with the quote check and repair.









<!-- page 25 -->


     M3-T4: Pass B with schema validation, repair and the unsorted path.
     M3-T5: The embedding adapter and shortlist retrieval.
     M3-T6: Matching, with the decisions log.
     M3-T7: The commit transaction, using the M1 rules, followed by embedding.
     M3-T8: Reprocess and retract, wired to the API.

Done when the scorecard meets its targets, and processing the same source twice leaves
identical row counts.

M4: Map layout and read API

     M4-T1: Region shapes with seeded borders, stored as layout version 1.
     M4-T2: The placement algorithm, with tests for determinism, no overlaps and pinned
     existing landmarks.
     M4-T3: The layout stage in the pipeline.
     M4-T4:   GraphStore       with an in-memory implementation.
     M4-T5:   GET /map     , the node and evidence endpoints, and the media link.

Done when every active concept from the fixtures sits inside its home region, and adding
a second source moves no existing landmark.

M5: Web map

     M5-T1:   MapRenderer      with regions, landmarks, zoom levels and labels.
     M5-T2: Type icons, size, fade, status outlines and a legend.
     M5-T3: Selection, neighbour lines, the evidence panel, audio playback from a quote,
     and the transcript link.
     M5-T4: Filters.
     M5-T5: A Playwright test that signs in, uploads fixture text, waits for              ready   , opens
     the map, selects a landmark and reads a quote.

Done when the Playwright test passes and every hypothesis shows its label in the panel.

M6: First real session

     M6-T1: Deployment, if the owner wants V1 hosted: container images, managed
     Postgres, a storage bucket, HTTPS and secrets.
     M6-T2: Backups: a scheduled database dump and versioning on the bucket.
     M6-T3: The owner uploads one real therapy session. Claude Code does not handle real
     data.













<!-- page 26 -->


     M6-T4: The owner checks 30 random statements and 30 random concepts against the
     transcript, and records findings in        docs/DECISIONS.md         in general terms.
     M6-T5: Tune prompts and thresholds against the synthetic fixtures to address the
     findings.

Done when the owner can open any item on the map and read the quotes behind it. That is
the V1 exit.

Later phases

Each later phase adds tables, jobs or views beside the V1 foundations. None of them
changes the four layers. This section is for orientation only and is not to be built during V1.

Phase 2: the atlas becomes useful

     More inputs and bulk import. One importer per archive format, each producing
     sources and segments. The pipeline after that point is unchanged. Bulk runs use the
     model provider's batch interface.
     Analysis jobs. These run after each commit and read one user's graph through
     GraphStore     . Their output is derived data: each run replaces the previous run's
     output.
     Themes. Cluster the concepts inside each region with a community-detection
     algorithm. The model names each cluster. New tables:               themes    and  theme_members       .
     Theme ids stay stable through the overlap matching described under "The map".
     Patterns. Mine recurring sequences across Events, using the order on                   OCCURRED_IN
     and the   LED_TO    links. A sequence seen in events from two or more sources becomes
     a Pattern node with      HAS_STEP     and  SEEN_IN     links. Pattern cards show the steps and
     the events behind them.
     Tensions. Built from     contradicts       evidence and     CONFLICTS_WITH        links.
     Blind spots. Built from concepts whose status is            observed     or  hypothesis      and
     whose evidence spans two or more sources.
     Unsorted view. Lists misfits grouped by suggested type, so the owner can see what
     the vocabulary lacks.
     Export. One archive holding a manifest, one JSON Lines file per table, the vocabulary
     file, the original media and the raw provider responses. A matching import command
     restores it into an empty instance.




















<!-- page 27 -->


Phase 3: conversation and more views

     Mirror chat. Retrieval embeds the message, finds the nearest statements and
     concepts, expands one or two steps through              GraphStore     , and gathers the quotes.
     The answer cites concepts and quotes, and keeps each item's status label.
     Write-back. Each conversation is a source of kind             chat   . Only the owner's turns
     become segments. The AI's turns are stored for display and never enter the pipeline.
     Distress. If a message signals acute distress, the chat stops reflecting patterns and
     points to appropriate support. This behaviour is specified and tested before the chat
     ships.
     Neo4j decision point. Add Neo4j as a read-only copy if path queries against Postgres
     have become hard to maintain, or if chat needs free-form graph queries. The work is a
     projector that upserts nodes and relationships by id after each commit, a full rebuild
     command, and a second          GraphStore      implementation.
     Network graph and timeline. Two more read-only views over the same API.

Phase 4: the atlas comes to the owner

     Summaries, digests and briefs. Scheduled jobs write to a new                 insights      table from
     the analysis output.
     Coach and challenger modes. Extra chat stances chosen per conversation. Retrieval
     is unchanged.
     Framework overlays. A new           overlay_labels       table maps core concepts to a
     framework's terms. The core vocabulary does not change, and overlays can be
     toggled on the map.

Phase 5: more signal, more devices

     Tone and visual analysis. A new         annotations      table keyed to segments, filled by a
     ToneAnalyser       provider reading the stored original media. A later pipeline version can
     pass annotations to extraction as extra context.
     Mobile. A client of    /api/v1    . Capture uses the same signed-link upload.

Phase 6: other users

     Accounts. Sign-up and an identity provider. Row-level security already isolates data.
     Consent. A     consents     table for recordings that include other people.
     Privacy tiers. Each tier selects provider adapters and settings. ElevenLabs
     documents a zero-retention mode that fits a stricter tier.
     Curated exports. Named filters over the full export, such as values, needs and traits
     with no quotes and no other people. Every export is logged.








<!-- page 28 -->


     Legal review. The product will hold health-related personal data about users and
     about people they mention. It needs legal review before launch.

Testing and evaluation

Ordinary code is covered by tests. Extraction quality is covered by a scorecard against
synthetic fixtures, because it cannot be judged as a simple pass or fail.

Tests

     Unit tests for the rules module, validators, segment builder, matching logic and layout.
     Database tests for user isolation, clean retraction and all-or-nothing commits.
     A full pipeline run on a fixture with fake providers, plus a check that running twice
     gives identical row counts.
     Provider adapters are tested against recorded responses. One live smoke test per
     adapter is run by hand with        make smoke     .
     Component tests for the evidence panel and one Playwright end-to-end test.
     CI runs everything except live calls.

Fixtures

Every fixture is invented. Each has a transcript and a file of expected statements,
concepts and relationships. The fixtures include these hard cases on purpose:

     A therapist observation the owner never echoes, which should come out as
     observed     .
     A feeling that is implied but never named, which should come out as                   hypothesis     .
     A belief stated in one place and contradicted in another.
     A diagnosis stated by the therapist, which is allowed, and a description that might
     tempt one, which must not produce one.
     One person referred to by two names.
     An upcoming event and a formative past event.
     Small talk and scheduling, which should produce nothing.

Scorecard


  Measure                       How it is measured                                       Target

  Quote validity                Stored statements whose quote is an exact                100%, enforced
                                substring of the segment

  Speaker attribution           Statements carrying the correct speaker role             100%











<!-- page 29 -->



  Measure                      How it is measured                                       Target

  Statement recall             Expected statements matched by a stored                  85% or more
                               one with an overlapping quote

  Concept recall               Expected concepts found with the same                    80% or more
                               type and a matching name or alias

  Concept precision            A sample of stored concepts judged                       90% or more
                               supported by their cited statements

  Type accuracy                Matched concepts with the correct type                   90% or more

  Status accuracy              Matched concepts correctly marked stated,                90% or more
                               observed or hypothesis

  Duplicate rate               Stored nodes that the expected file treats as            5% or less
                               one concept

  Life-area agreement          Matched concepts placed in the expected                  80% or more
                               home area

  Diagnosis rule               Count                                                    0, enforced
  violations

  Dropped items                Statements and mentions removed by                       Reported, no
                               validators                                               target


The targets are starting values proposed in this plan. Revise them after the first real
session.

Running it

     make eval      calls the live model and prints the scorecard. Run it whenever a prompt,
     model or threshold changes.
     Each run appends a line to        evals/history.jsonl          with the prompt, model and
     schema versions, so regressions are visible.
     Claude Code's bundled         /claude-api      skill has  build-eval      and   hillclimb
     workflows that can help build and improve against this harness. source

The real-session check

In M6 the owner reviews 30 random statements and 30 random concepts from the real
session. Each problem is classed as wrong quote, wrong speaker, wrong type, over-reach,
duplicate or missing. Only the classes and counts are written down. Each class of problem
then becomes a new synthetic hard case.














<!-- page 30 -->

Security and privacy

The system holds therapy recordings. V1 protects them with sign-in, per-user isolation,
private storage, and a rule that content never reaches logs or the repository.

In V1

     Sign-in. Argon2 password hashing, server-side sessions, cookies set to HttpOnly,
     Secure and SameSite, protection against cross-site request forgery, and a rate limit on
     login.
     Isolation. Every query runs with the session's user set. Row-level security denies
     everything else. The application's database role cannot bypass it.
     Storage. The bucket is private. Files are reached only through signed links that expire
     within five minutes.
     Transport and rest. HTTPS everywhere once deployed. Encryption at rest comes from
     the database and storage providers.
     Secrets. Environment variables only. Never committed.
     Logs. Ids, counts, durations and error codes. If an error-reporting tool is added, it
     must be set to drop request and response bodies.
     Deletion. Retracting a source deletes its media and derived rows. Backups expire
     after 30 days, so deleted data leaves the backups within that time.

What each provider receives


  Provider                 Receives                           Check before real data

  ElevenLabs               The derived audio file             Retention settings. The vendor
                                                              documents a zero-retention mode.
                                                              source

  Anthropic                Transcript text and                Retention terms on the API account
                           statements

  Embedding                Statement and concept              Retention terms on the account
  provider                 text


Real data and Claude Code

     Real recordings and transcripts never enter the repository. Local copies live in                   data/   ,
     which is git-ignored.
     Claude Code is denied read access to            data/    and   .env   through its settings file.
     Tests, fixtures and evaluation use invented material only.













<!-- page 31 -->


     When something fails on real data, the owner passes Claude Code ids, counts and
     error codes, not content.

Before hosting real data on the public internet

     Add a second sign-in factor.
     Confirm the retention settings in the table above.
     Confirm backups restore.

Deferred, with room left

     Application-level encryption of transcript and statement text with per-user keys. All
     access to those columns goes through the              db   layer, so this can be added in one place.
     A log of who read what.
     Consent records for recordings that include other people.

Instructions for Claude Code

The repository is the project's memory. Every Claude Code session starts with an empty
context, so anything that must survive between sessions is written to a file in the
repository.

The facts about Claude Code below were checked on 25 November 2026 against its
memory documentation and skills documentation.

How memory is organised


  File                                            Holds                             When it is read

  CLAUDE.md                                       Standing facts and rules.         Every session, and
                                                  Under 200 lines                   again after
                                                                                    compaction

  .claude/rules/*.md                              Rules for one part of the         When a matching file
                                                  code                              is opened

  .claude/skills/*/SKILL.md                       Procedures: session               When invoked
                                                  start, session end, verify

  docs/PROGRESS.md                                Current milestone, task           At session start,
                                                  ticks, next step, session         through the skill
                                                  log

  docs/DECISIONS.md                               Choices made after this           When relevant
                                                  plan, and any deviation
                                                  from it








<!-- page 32 -->



 File                                           Holds                            When it is read

  docs/plan/IMPLEMENTATION_PLAN.md              This plan                        One section at a time,
                                                                                 as needed


Three points shape this design:

     CLAUDE.md     is guidance, not enforcement. Hard limits go in          .claude/settings.json
    as deny rules.
    An   @path    import loads the imported file in full with       CLAUDE.md    . So  CLAUDE.md     names
    this plan in backticks and never imports it.
    Claude Code's auto memory is stored outside the repository, on one machine. It is fine
    for the owner's preferences. It is never the only place a project fact is kept.

Setup steps (task M0-T1)

  1. Confirm this plan is saved at      docs/plan/IMPLEMENTATION_PLAN.md             .
  2. Create   CLAUDE.md     from the template below. Do not generate it with            /init   .
  3. Create the four rule files listed below.
  4. Create the three skills below.
  5. Create   .claude/settings.json          from the template below. Check the rule syntax
    against the permissions documentation.
  6. Create   docs/PROGRESS.md        and  docs/DECISIONS.md         from the templates below.
  7. Add   data/  , .env   , CLAUDE.local.md       and  .claude/settings.local.json             to
     .gitignore     .
  8. Run  /context all       and confirm    CLAUDE.md      is listed under memory files.
  9. Commit as     M0-T1: memory setup         and stop for the owner's review.

Template: CLAUDE.md

  # Mental Atlas

  A personal atlas of the owner's mind, built from therapy recordings and
  writing.
  Specification: `docs/plan/IMPLEMENTATION_PLAN.md`. Read the section you are
  working on before changing code.

  ## State
  - Current state and next task: `docs/PROGRESS.md`
  - Decisions and deviations: `docs/DECISIONS.md`
  - Vocabulary: `ontology/atlas.yaml` (readable copy: `docs/ONTOLOGY.md`)










<!-- page 33 -->



 ## Session routine
 - Start every session with /session-start.
 - End every session, and before context is compacted, with /session-end.
 - One task per commit. Prefix the message with the task id (M2-T3: ...).

 ## Commands
 - make dev       start API, worker, web, Postgres, MinIO
 - make verify    lint, types, tests, generated-file check; must pass before
 every commit
 - make generate  regenerate code from the vocabulary and the API schema
 - make migrate   apply migrations
 - make eval      live extraction scorecard; costs money, ask first

 ## Layout
 - backend/atlas: api, domain (generated models, rules), db, pipeline,
 providers, graph
 - web/src: map, sources, generated API client
 - evals: synthetic fixtures and scorecard

 ## Rules that must never be broken
 1. Postgres is the only source of truth.
 2. Every table has user_id and a row-level security policy.
 3. Every atlas write carries a run_id. Retraction must stay exact.
 4. Never change meaning in place. Add rows.
 5. Never hand-edit generated files. Change ontology/atlas.yaml and run make
 generate.
 6. Vocabulary changes need the owner's approval.
 7. Every provider call goes through its interface. Tests use the fakes.
 8. Pipeline stages are idempotent and versioned.
 9. Never log, print or commit transcript text, quotes, or model input or
 output.
 10. Never read data/ or .env. Use only invented fixtures.
 11. AI inferences are stored and shown as hypotheses. The AI never creates a
 diagnosis.

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









<!-- page 34 -->


Rule files

Each file starts with a     paths    list in its frontmatter, so it loads only when matching files
are opened.


  File                                   Paths                                       Contents

  .claude/rules/database.md              backend/atlas/db/**        ,                 user_id    and a
                                         backend/alembic/**                          security policy on
                                                                                     every table, in the
                                                                                     same migration.
                                                                                     Merged migrations
                                                                                     are never edited.
                                                                                     Time-ordered UUIDs.
                                                                                     UTC

  .claude/rules/pipeline.md              backend/atlas/pipeline/**          ,        Idempotent stages.
                                         backend/atlas/providers/**                  A   run_id   on every
                                                                                     write. Code validates
                                                                                     all model output.
                                                                                     Prompt changes
                                                                                     raise the prompt
                                                                                     version. No content
                                                                                     in logs

  .claude/rules/ontology.md              ontology/**     ,                           Generated files are
                                         backend/atlas/domain/**                     not edited by hand.
                                                                                     Vocabulary changes
                                                                                     need approval and a
                                                                                     version bump

  .claude/rules/web.md                   web/**                                      API access only
                                                                                     through the
                                                                                     generated client. The
                                                                                     map renders only
                                                                                     through
                                                                                      MapRenderer     . A
                                                                                     hypothesis always
                                                                                     shows its label


Template: skills

.claude/skills/session-start/SKILL.md














<!-- page 35 -->



 ---
 name: session-start
 description: Load project state at the start of a working session. Use at the
 beginning of every session, before any code change.
 ---
 1. Read docs/PROGRESS.md.
 2. Run git status and git log --oneline -15.
 3. In docs/plan/IMPLEMENTATION_PLAN.md, read the current milestone and any
    section the current task depends on.
 4. If PROGRESS.md and git disagree, trust git, correct PROGRESS.md and say
 so.
 5. State the task, the files you expect to touch and how you will verify it.
    Then begin.


.claude/skills/session-end/SKILL.md

 ---
 name: session-end
 description: Save project state at the end of a working session, or before
 context is compacted.
 ---
 1. Run make verify. Fix failures, or record them under Known issues.
 2. In docs/PROGRESS.md: tick finished tasks, update the Now block, and add a
    session log entry with what was done, how it was verified, what is
    unfinished and what comes next.
 3. Append to docs/DECISIONS.md every choice the plan did not make and every
    deviation from the plan.
 4. Commit. Leave no uncommitted work.


.claude/skills/verify/SKILL.md

 ---
 name: verify
 description: Check that the working tree is ready to commit.
 ---
 Run make verify. Report each failure with its file and line.
 Do not commit while it fails.

Claude Code tells Claude to run a project skill named        verify    before each commit, apart
from changes to docs or tests. That is why this one has that name.























<!-- page 36 -->


Template: .claude/settings.json

 {
   "permissions": {
     "deny": [
       "Read(./.env)",
       "Read(./.env.local)",
       "Read(./data/**)"
     ]
   }
 }


Template: docs/PROGRESS.md

 # Progress

 ## Now
 - Milestone: M0 Foundations
 - Current task: M0-T1
 - Next step: (one sentence)
 - Blocked on: nothing

 ## Milestones
 - [ ] M0 Foundations
 - [ ] M1 Vocabulary and database
 - [ ] M2 Ingestion
 - [ ] M3 Extraction
 - [ ] M4 Map layout and read API
 - [ ] M5 Web map
 - [ ] M6 First real session

 ## Tasks in the current milestone
 (copy the task list for the current milestone from the plan)


 ## Session log (newest first, keep the last 10)
 ### YYYY-MM-DD
 - Done:
 - Verified by: (command and result)
 - Unfinished:
 - Next:

 ## Known issues


















<!-- page 37 -->


Template: docs/DECISIONS.md

  # Decisions

  Append only. Decisions already made in the plan are not repeated here.
  Never edit an earlier entry. Add a new one that supersedes it.


  ## D-001 (YYYY-MM-DD) Title
  - Context:
  - Decision:
  - Reason:
  - Alternatives considered:
  - Approved by owner: yes / not needed


Working rules

     Work one task at a time: read, plan, implement, verify, commit.
     Write tests first for the rules module, the validators and the layout.
     Never mark a task done without naming the command that was run and its result.
     Keep a session to one milestone or less. Start a fresh session for each milestone.
     After compaction,      CLAUDE.md      is re-read from disk, but instructions given only in
     conversation are lost. Write anything that matters to            PROGRESS.md      or  DECISIONS.md
     before then.
     When the owner gives the same correction twice, add it to                CLAUDE.md     or a rule file. If
     it must hold every time, propose a deny rule or a hook.
     Keep   CLAUDE.md      under 200 lines. Move part-specific material to rule files and
     procedures to skills.
     Before using any library or provider API, check its current documentation. Model ids
     and versions come from configuration.
     At the end of each milestone, run its "Done when" checks, write a short report in
     PROGRESS.md      , and stop for the owner's review.

Risks and open questions

The largest risk is an atlas that is wrong and trusted anyway, because nothing is reviewed
on the way in. Most of the mitigations below exist to keep every item checkable.






















<!-- page 38 -->




  Risk                                   Why it matters                        Mitigation

  Extraction over-reaches                An inference is stored as if          The   basis    field, hypothesis
                                         the owner said it                     labels, quotes on every item,
                                                                               the status-accuracy measure,
                                                                               the M6 review

  Speaker roles are swapped              A whole session is                    The 0.9 threshold, the voice
                                         attributed to the wrong               check, swap and reprocess
                                         person

  Concepts are duplicated or             Counts and later patterns             Cautious matching, the
  wrongly merged                         become unreliable                     decisions log, reversible
                                                                               merges, the duplicate-rate
                                                                               measure

  The map becomes cluttered              The owner loses their                 Fixed regions, pinned
  or unstable                            sense of place                        positions, zoom levels, stable
                                                                               themes in phase 2

  The first map looks thin               V1 is judged on richness,             The V1 exit is the chain from
                                         which one session cannot              map item to quote, not the
                                         give                                  amount of content

  Transcription errors in names          Quotes are wrong at the               The key-term list, audio
  or emotional speech                    source                                playback beside every quote,
                                                                               a swappable provider

  Providers change models,               Results drift without                 Ids in configuration, raw
  prices or behaviour                    notice                                responses kept, versions on
                                                                               every run, the evaluation
                                                                               history

  Sensitive content leaks                Serious personal harm                 Design rule 9, deny rules,
  through logs, fixtures or an                                                 invented fixtures, the owner
  agent's context                                                              handles real data

  Reading AI hypotheses                  The tool could harm the               Clear labels, the mirror
  about oneself is unsettling or         person it is for                      stance, and reviewing the
  misleading                                                                   first real output with the
                                                                               therapist


Open questions for the owner



















<!-- page 39 -->




     Decide whether V1 is hosted or runs locally until phase 2. This decides task M6-T1.
     Choose the embedding provider.
     Confirm sessions are in English. The prompts and fixtures assume it.
     Confirm whether any recording has a third voice, such as a partner in a joint session.
     Accept or change the clockwise order of life areas on the map.
     Accept or change the scorecard targets.
     Confirm retention settings with ElevenLabs, Anthropic and the embedding provider
     before uploading real data.

Sources

     ElevenLabs, Introducing Scribe v3 and v3 Live, published 10 November 2026.
     Claude Code documentation, How Claude remembers your project.
     Claude Code documentation, Extend Claude with skills.



















































































```
