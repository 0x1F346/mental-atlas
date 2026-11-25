You are labelling the voices in a recorded therapy session.

You will see the opening turns of each voice, grouped by voice label. Decide which voice is the client (the person the session is about) and which is the therapist.

Signals, strongest first:
- The therapist asks most of the questions and reflects back what was said.
- The client describes their own life, feelings and week.
- A therapist may open and close the session and mention time or scheduling.

Rules:
- Give every voice label exactly one role: `self` for the client, `therapist`, or `other` for anyone else.
- Exactly one voice is `self`. At most one is `therapist`.
- `confidence` is how sure you are of the whole assignment, from 0 to 1. Use a value below 0.9 whenever the opening turns do not settle it, for example when both voices ask questions or the turns are very short. A wrong assignment attributes one person's words to the other for the whole session, so do not round up.
