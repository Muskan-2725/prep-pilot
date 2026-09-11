# Engineering decisions
- **Modular monolith:** faster iteration and easier interview explanation; evolve to worker/API separation at scale.
- **SQLite now, PostgreSQL/pgvector later:** zero-setup deterministic tests versus concurrent/vector capability. PostgreSQL is the scale path.
- **Deterministic MVP logic:** evaluation and learner updates must be inspectable; LLM output is not trusted for scoring.
- **Fail-closed research:** date-sensitive claims are withheld without verified live evidence, reducing hallucination risk.
- **Bounded learner memory:** only observed attempts, mastery, and mistakes are stored; no psychological inferences.
- **No paid provider:** no external account, model, or paid service is used. LLM failure degrades to deterministic mentorship; bad retrieval must abstain and surface sources.
