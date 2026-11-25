# Synthetic fixtures

Every person, event and sentence here is invented. No real recording or transcript is ever placed in this directory.

Each fixture is a pair of files:

- `<name>.transcript.json`: the source. `turns` are `[speaker, text]` pairs with speaker `self` or `therapist`; a journal has `paragraphs` instead.
- `<name>.expected.json`: what extraction should produce.
  - `statements`: `segment` is the index of the turn or paragraph, `quote` is a verbatim excerpt of it.
  - `concepts`: `match` lists lower-case fragments; a stored concept matches when its name or an alias contains any of them. `status` and `home` are the expected computed values. `evidence` refers to statement keys.
  - `relationships`: `from` and `to` are concept keys; `me` is the owner's own Person node.
  - `silent_segments`: small talk and scheduling, which should produce nothing.
  - `forbidden`: concepts that must not appear, such as a diagnosis nobody stated.

The hard cases the plan asks for, and where they are:

| Hard case | Fixture | Concept key |
| --- | --- | --- |
| Therapist observation the owner never echoes (`observed`) | session_one | `found_out` |
| Feeling implied but never named (`hypothesis`) | session_one | `shame` |
| Belief stated in one place and contradicted in another | session_one | `not_good_enough` |
| Diagnosis stated by the therapist (allowed) | session_one | `gad` |
| Description that might tempt a diagnosis (must not produce one) | session_one | `forbidden` |
| One person referred to by two names | session_two | `mum` |
| Upcoming event and formative past event | session_one | `offsite`, `dinner` |
| Small talk and scheduling produce nothing | all | `silent_segments` |

`audio/two_voice_session.m4a` is an invented dialogue read by two text-to-speech voices, used by the browser test.
