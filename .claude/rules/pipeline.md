---
paths:
  - "backend/atlas/pipeline/**"
  - "backend/atlas/providers/**"
---

# Pipeline and provider rules

- Stages are idempotent and versioned, keyed by source, stage and pipeline version. Running a stage again first retracts the earlier run for that key.
- Every write carries the `run_id` of the run that produced it.
- Code validates all model output: quotes are exact substrings of their segment, types and endpoints match the vocabulary, every mention cites a statement. Prompts alone are never the enforcement.
- The speaker role is copied from the segment. The model never chooses it.
- Changing a prompt raises its prompt version. Prompts are versioned files under `backend/atlas/pipeline/prompts/`.
- Every outside provider is called through its interface (`Transcriber`, `ExtractionModel`, `Embedder`, `BlobStore`). Tests use the fakes.
- Raw provider responses are kept in object storage.
- Model ids and versions come from configuration, never from literals in code.
- No content in logs: no transcript text, quotes, or model input or output. Logs carry ids, counts, durations and error codes only.
