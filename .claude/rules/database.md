---
paths:
  - "backend/atlas/db/**"
  - "backend/alembic/**"
---

# Database rules

- Every table has `id` (UUID), `user_id` and `created_at`.
- Every table gets its row-level security policy in the same migration that creates it. No table exists, even briefly, without one.
- The application's database role must not be able to bypass row-level security.
- One migration per change. A merged migration is never edited; add a new one.
- Ids are time-ordered UUIDs.
- Times are stored in UTC.
- Every atlas write carries a `run_id`, so retracting a run removes exactly what it wrote.
- Meaning is never changed in place. New evidence and contradictions add rows.
