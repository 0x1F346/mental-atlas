You are extracting statements from a transcript for a personal atlas of one person's inner life. That person is the owner, marked ME. A session may also include their THERAPIST or OTHER speakers.

The full transcript is given for context. You will be asked about one window of segments at a time. Record only statements whose quote lies in a segment of that window.

A statement is one single thing that was said. For each statement give:
- `segment`: the id of the segment the quote comes from, such as S12.
- `quote`: a verbatim excerpt of that segment, copied character for character. Never paraphrase, correct, join or trim words inside the quote. Keep it to the clause or sentence that carries the claim.
- `text`: the same claim restated so it makes sense on its own, with pronouns and references resolved from the rest of the transcript. Keep the speaker's meaning; add nothing.
- `kind`: `report` for what happened; `feeling` for how it felt; `reflection` for an interpretation or realisation; `intention` for what the speaker means to do; `observation` for a therapist's remark about the owner.
- `about_time_text`: when the thing described happened, in the speaker's words ("when I was nine", "last Sunday"), or null.
- `about_from` and `about_to`: that period as ISO dates when it can be worked out from the session date, otherwise null.
- `confidence`: 0 to 1.

Rules:
- Split a segment that says several things into several statements, each with its own quote.
- Skip pleasantries, logistics and scheduling. They produce nothing.
- A therapist's question becomes a statement only when it carries an observation about the owner ("It sounds like you expect to be found out"). A plain question ("What happened next?") produces nothing. Every therapist statement has kind `observation`.
- The owner's statements never have kind `observation`.
- Do not interpret. If the owner did not say they felt something, do not write that they did; a later step handles inference and labels it as such.
- Never record a statement you cannot back with an exact quote.
