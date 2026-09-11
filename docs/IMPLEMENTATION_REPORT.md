# V1 implementation report

## Real V1 capabilities
- Persistent SQLite learner model: profile, exam goal/date/hours, topic confidence/mastery/trend, attempts, mistake type, plans and messages.
- Browser practice flow with answer selection, confidence, self-reported mistake taxonomy, evaluation feedback, and an updated dashboard/plan.
- Adaptive topic priority: planner/practice/mentor use the same learner state; priority uses mastery, onboarding confidence, and recent topic accuracy.
- Honest research fallback: no live search is claimed. A static official GATE source is returned with `confidence: unavailable`.

## Explicit limits
There is no LLM, live web retrieval, embeddings, vector search, document ingestion, or model-generated citation in this zero-cost local V1. Mentor answers are deterministic and expose that mode. Questions are authored seed data, not previous-year paper content. There is no server-side logout/revocation or public deployment configuration.
